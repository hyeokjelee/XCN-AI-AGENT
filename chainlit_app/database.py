"""SQLite 기반 영속화 계층.

- Chainlit Data Layer용 테이블(users/threads/steps/elements/feedbacks)
- 로그인 자격증명용 app_users 테이블(bcrypt 해시)

모든 데이터는 단일 sqlite 파일(chainlit.db)에 저장된다.
LangGraph 체크포인터는 별도 sqlite 파일(checkpoints.db)을 사용한다.
"""
import os
import sqlite3
from datetime import datetime, timezone

import bcrypt

# 데이터 레이어 + 로그인 자격증명 DB
CHAINLIT_DB_PATH = os.getenv("CHAINLIT_DB_PATH", "/app/database/chainlit.db")
# LangGraph 체크포인터 DB (기존 main.py와 동일 파일)
CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "/app/database/checkpoints.db")

# Chainlit SQLAlchemyDataLayer가 기대하는 스키마(SQLite 호환)
_CHAINLIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT NOT NULL,
    "createdAt" TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "metadata" TEXT,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "parentId" TEXT,
    "streaming" INTEGER NOT NULL,
    "waitForAnswer" INTEGER,
    "isError" INTEGER,
    "metadata" TEXT,
    "tags" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "command" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" TEXT,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INTEGER,
    "defaultOpen" INTEGER,
    "autoCollapse" INTEGER,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INTEGER,
    "language" TEXT,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "value" INTEGER NOT NULL,
    "comment" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);
"""

_APP_USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_users (
    "identifier" TEXT PRIMARY KEY,
    "password_hash" TEXT NOT NULL,
    "display_name" TEXT,
    "role" TEXT DEFAULT 'user',
    "created_at" TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """필요한 모든 테이블을 생성한다(이미 있으면 무시)."""
    os.makedirs(os.path.dirname(CHAINLIT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        conn.executescript(_CHAINLIT_SCHEMA)
        conn.executescript(_APP_USERS_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_user(identifier: str, password: str, display_name: str | None = None,
                role: str = "user") -> None:
    """로그인 사용자 추가/갱신(비밀번호는 bcrypt 해시 저장)."""
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        conn.execute(
            """INSERT INTO app_users (identifier, password_hash, display_name, role, created_at)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(identifier) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    display_name=excluded.display_name,
                    role=excluded.role""",
            (identifier, pw_hash, display_name or identifier, role, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def verify_user(identifier: str, password: str) -> dict | None:
    """자격증명 검증. 성공 시 사용자 정보 dict, 실패 시 None."""
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute(
            "SELECT password_hash, display_name, role FROM app_users WHERE identifier = ?",
            (identifier,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    pw_hash, display_name, role = row
    if not bcrypt.checkpw(password.encode("utf-8"), pw_hash.encode("utf-8")):
        return None
    return {"identifier": identifier, "display_name": display_name, "role": role}


# ---------------------------------------------------------------------------
# 관리자용 조회/관리 함수
# ---------------------------------------------------------------------------

def list_users() -> list[dict]:
    """모든 로그인 사용자 목록."""
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute(
            "SELECT identifier, display_name, role, created_at FROM app_users ORDER BY created_at"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"identifier": r[0], "display_name": r[1], "role": r[2], "created_at": r[3]}
        for r in rows
    ]


def delete_user(identifier: str) -> bool:
    """로그인 사용자 삭제. 삭제되면 True."""
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute("DELETE FROM app_users WHERE identifier = ?", (identifier,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_admins() -> int:
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM app_users WHERE role = 'admin'")
        return cur.fetchone()[0]
    finally:
        conn.close()


def list_all_threads() -> list[dict]:
    """모든 사용자의 세션(스레드) 목록 + 메시지 수."""
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute(
            """
            SELECT t.id, t.name, t."userIdentifier", t."createdAt",
                   (SELECT COUNT(*) FROM steps s
                      WHERE s."threadId" = t.id
                        AND s.type IN ('user_message', 'assistant_message')) AS msg_count
            FROM threads t
            ORDER BY t."createdAt" DESC
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "name": r[1], "user": r[2], "created_at": r[3], "messages": r[4]}
        for r in rows
    ]


def get_thread_messages(thread_id: str) -> list[dict]:
    """특정 세션의 대화 메시지(사용자/어시스턴트)."""
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    try:
        cur = conn.execute(
            """
            SELECT type, name, output, "createdAt"
            FROM steps
            WHERE "threadId" = ?
              AND type IN ('user_message', 'assistant_message')
            ORDER BY "createdAt" ASC, id ASC
            """,
            (thread_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    for type_, name, output, created in rows:
        role = "user" if type_ == "user_message" else "assistant"
        result.append({"role": role, "name": name, "content": output or "", "created_at": created})
    return result
