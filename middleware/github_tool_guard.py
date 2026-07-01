"""GitHub 도구 호출 자동 교정 + 필수 인자 검증 + 반복 호출 차단 미들웨어.

로컬 LLM이 GitHub MCP 도구에서 반복적으로 내는 결정론적 오류를 도구 호출 직전에
코드로 바로잡거나, 고칠 수 없는 경우 'API를 때리지 않고' 구체적 수정 안내 메시지를
돌려줘 무한 재시도 루프를 끊는다. (실제 로그 분석 기반)

[자동 교정 — 인자를 고쳐서 그대로 실행]
1) get_file_contents/list_branches/list_commits/list_pull_requests/pull_request_read
   처럼 읽기 전용 도구에서 owner 누락 → 기본 조직(XCURENETGIT) 주입
2) create_or_update_file 의 content 가 비어 있음 → "# <repo>\n" 최소 내용 주입
3) pull_request_read 에 path 등 파일조회용 잉여 인자 혼입 → 제거
4) search_repositories 쿼리의 값 없는 빈 한정자(`language:` 등) → 제거

[검증 차단 — API 호출 없이 수정 안내 ToolMessage 반환]
5) create_or_update_file 등에서 필수 인자(owner/repo/path/content/message…) 누락
   → 누락 필드 목록 + 올바른 호출 템플릿을 돌려줘 한 번에 채우게 한다
6) 쓰기 도구에서 owner 누락 → 추측 주입 금지(엉뚱한 곳에 쓰기 방지), 명시 요구
7) 조직 저장소에서 owner==repo(둘 다 XCURENETGIT) → repo 에 실제 저장소명 요구
8) search 쿼리의 user:/org: 값이 placeholder(current-user 등) → get_me 안내

[반복 차단]
같은 (thread, tool, args) 가 WINDOW 내 STOP_AT 회 이상 반복되면 중단 메시지 반환.

교정/차단이 일어나면 tool_log 와 github_tool_guard.log 에 기록한다.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

# 고정 조직(에이전트 활동 범위). 개인 작업의 owner 는 get_me 의 login 이며 추측 주입하지 않는다.
ORG = "XCURENETGIT"

# 도구별 필수 인자 (MCP 서버의 github_ prefix 는 매칭 시 제거).
REQUIRED = {
    "create_or_update_file": ["owner", "repo", "path", "content", "message", "branch"],
    "delete_file":           ["owner", "repo", "path", "message", "branch"],
    "get_file_contents":     ["owner", "repo", "path"],
    "list_branches":         ["owner", "repo"],
    "create_branch":         ["owner", "repo", "branch"],
    "list_commits":          ["owner", "repo"],
    "create_pull_request":   ["owner", "repo", "title", "head", "base"],
    "pull_request_read":     ["method", "owner", "repo", "pullNumber"],
    "list_pull_requests":    ["owner", "repo"],
    "update_pull_request":   ["owner", "repo", "pullNumber"],
    "merge_pull_request":    ["owner", "repo", "pullNumber"],
}

# owner 누락 시 ORG 자동 주입이 안전한 읽기 전용 도구.
# (쓰기 도구는 추측 주입하면 엉뚱한 저장소에 쓰므로 주입하지 않고 명시를 요구한다.)
READ_OWNER_INJECTABLE = {
    "get_file_contents", "list_branches", "list_commits",
    "list_pull_requests", "pull_request_read",
}

# pull_request_read 에 허용되는 인자(그 외 path 같은 파일조회 인자는 제거).
PR_READ_ALLOWED = {"method", "owner", "repo", "pullNumber", "page", "perPage"}

# search 쿼리에서 user:/org: 값으로 들어오면 안 되는 placeholder.
BAD_OWNER_TOKENS = {
    "current-user", "username", "user", "me", "login",
    "<username>", "<login>", "<owner>", "your-username",
}

# 반복 차단 파라미터
_WINDOW = 90.0
_STOP_AT = 3
_MAX_KEYS = 1000


class GithubToolGuardMiddleware(AgentMiddleware):
    def __init__(self, log_dir: str = "/app/tmp/tool_log"):
        self.log_dir = Path(log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._repeat: dict = {}  # key -> {ts0, count}

    async def awrap_tool_call(self, request, handler):
        raw_name = request.tool_call.get("name", "")
        name = raw_name.removeprefix("github_")
        if name not in REQUIRED and name != "search_repositories":
            return await handler(request)  # 가드 대상 외 도구는 그대로 통과

        args = dict(request.tool_call.get("args") or {})
        before = json.dumps(args, sort_keys=True, ensure_ascii=False)

        # 1) 자동 교정 (인자 수정)
        try:
            if name == "search_repositories":
                block = self._fix_search(request, args)
                if block is not None:
                    return block
            else:
                self._fix_common(name, args)
        except Exception as e:
            logger.warning(f"GithubToolGuard 교정 건너뜀: {e}")

        # 2) 필수 인자 검증 (누락이면 API 호출 없이 수정 안내 반환)
        try:
            block = self._validate(request, name, raw_name, args)
            if block is not None:
                return block
        except Exception as e:
            logger.warning(f"GithubToolGuard 검증 건너뜀: {e}")

        # 교정으로 args 가 바뀌었으면 반영 + 로깅
        after = json.dumps(args, sort_keys=True, ensure_ascii=False)
        if after != before:
            request.tool_call["args"] = args
            await self._log(request, "CORRECTED", f"BEFORE: {before}\n  AFTER : {after}")

        # 3) 반복 차단
        try:
            block = self._repeat_check(request, raw_name, args)
            if block is not None:
                return block
        except Exception as e:
            logger.warning(f"GithubToolGuard 반복체크 건너뜀: {e}")

        return await handler(request)

    # ---------- 자동 교정 ----------
    def _fix_common(self, name, args):
        # owner 누락 → 읽기 전용 도구에 한해 ORG 주입
        if name in READ_OWNER_INJECTABLE and not args.get("owner"):
            args["owner"] = ORG

        # create_or_update_file content 비어 있음 → 최소 내용 주입(빈 파일 생성 거부 방지)
        if name == "create_or_update_file":
            if not str(args.get("content", "")).strip():
                repo = args.get("repo") or "repo"
                args["content"] = f"# {repo}\n"

        # pull_request_read 잉여 인자(path 등) 제거
        if name == "pull_request_read":
            for k in list(args.keys()):
                if k not in PR_READ_ALLOWED:
                    args.pop(k, None)

    def _fix_search(self, request, args):
        """search 쿼리 정리. placeholder owner 면 안내 반환."""
        q = args.get("query")
        if not isinstance(q, str):
            return None
        tokens, dropped = [], False
        for tok in q.split():
            if ":" in tok:
                qual, _, val = tok.partition(":")
                if val == "":          # 값 없는 빈 한정자 → 제거
                    dropped = True
                    continue
                if qual in ("user", "org", "owner") and val.lower() in BAD_OWNER_TOKENS:
                    return self._guide(
                        request,
                        f"검색 쿼리의 `{qual}:{val}` 는 실재하지 않는 placeholder 입니다. "
                        f"개인 저장소는 `get_me` 로 확인한 실제 login 을, 조직은 `org:{ORG}` 를 "
                        f"쓰세요. 계정/조직명을 지어내지 마세요.",
                        "SEARCH_PLACEHOLDER",
                    )
            tokens.append(tok)
        cleaned = " ".join(tokens).strip()
        if not cleaned:
            return self._guide(
                request,
                f"검색 쿼리가 비어 있거나 유효한 한정자가 없습니다. 조직은 `org:{ORG}`, "
                f"개인은 `user:<get_me의 login>` 형식으로 쿼리를 채우세요.",
                "SEARCH_EMPTY",
            )
        if dropped:
            args["query"] = cleaned
        return None

    # ---------- 필수 인자 검증 ----------
    def _validate(self, request, name, raw_name, args):
        required = REQUIRED.get(name)
        if not required:
            return None

        # 쓰기 도구 owner 추측 주입 금지 → 명시 요구
        missing = [k for k in required if self._is_empty(args.get(k))]

        # owner==repo (조직 저장소 한정) → repo 자리에 조직명을 넣은 오류
        owner, repo = args.get("owner"), args.get("repo")
        if (owner and repo and str(owner) == str(repo) and str(owner) == ORG):
            return self._guide(
                request,
                f"`owner` 와 `repo` 가 모두 `{ORG}` 로 동일합니다. `repo` 에는 조직명이 아니라 "
                f"실제 저장소명을 넣어야 합니다(예: `repo='xcn_anomaly_detection'`). "
                f"저장소명을 모르면 먼저 `search_repositories`(`org:{ORG}`)로 확인하세요.",
                "OWNER_EQ_REPO",
            )

        if not missing:
            return None

        return self._guide(
            request,
            self._missing_guidance(name, missing, args),
            f"MISSING:{','.join(missing)}",
        )

    def _missing_guidance(self, name, missing, args):
        templates = {
            "create_or_update_file": (
                'create_or_update_file({"owner":"%s","repo":"<저장소명>","branch":"main",'
                '"path":"README.md","content":"# ...","message":"<커밋메시지>"})' % ORG
            ),
            "create_pull_request": (
                'create_pull_request({"owner":"%s","repo":"<저장소명>","title":"...",'
                '"head":"<작업브랜치>","base":"main"})' % ORG
            ),
        }
        tmpl = templates.get(name)
        msg = (f"`{name}` 호출에 필수 인자 {missing} 가 빠졌습니다. "
               f"인자를 나눠서 점진적으로 채우지 말고 **모든 필수 인자를 한 번에** 채워 "
               f"다시 호출하세요.")
        if tmpl:
            msg += f"\n올바른 형태: {tmpl}"
        if "owner" in missing:
            msg += (f"\nowner: 조직 작업이면 `{ORG}`, 개인 작업이면 `get_me` 로 확인한 login.")
        return msg

    @staticmethod
    def _is_empty(v):
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict)):
            return len(v) == 0
        return False

    # ---------- 반복 차단 ----------
    def _repeat_check(self, request, raw_name, args):
        now = time.monotonic()
        if len(self._repeat) > _MAX_KEYS:
            self._repeat = {k: v for k, v in self._repeat.items() if now - v["ts0"] <= _WINDOW}
        tid = self._get_thread_id(getattr(request, "runtime", None))
        try:
            akey = json.dumps(args, sort_keys=True, ensure_ascii=False)
        except Exception:
            akey = str(args)
        key = (tid, raw_name, akey)
        ent = self._repeat.get(key)
        if ent is None or now - ent["ts0"] > _WINDOW:
            self._repeat[key] = {"ts0": now, "count": 1}
            return None
        ent["count"] += 1
        if ent["count"] >= _STOP_AT:
            return self._guide(
                request,
                f"`{raw_name}` 를 동일한 인자로 {ent['count']}회 반복 호출했습니다. 같은 호출을 "
                f"다시 하지 말고, 직전 결과/오류 안내를 반영해 인자를 바꾸거나 다음 단계로 진행하세요.",
                f"REPEAT:{ent['count']}",
            )
        return None

    # ---------- 공통: 안내 메시지 + 로깅 ----------
    def _guide(self, request, text, tag):
        tcid = request.tool_call.get("id", "")
        name = request.tool_call.get("name", "")
        try:
            asyncio.create_task(self._log(request, "BLOCKED", f"[{tag}] {text}"))
        except RuntimeError:
            pass  # 실행 중 루프 없음(테스트 등) — 로깅 생략
        return ToolMessage(content=f"[가드] {text}", tool_call_id=tcid, name=name)

    async def _log(self, request, kind, detail):
        try:
            tid = self._get_thread_id(getattr(request, "runtime", None))
            name = request.tool_call.get("name", "")
            ts = datetime.now().isoformat()
            entry = f"[{ts}] [thread={tid}] GITHUB_GUARD_{kind} ({name})\n  {detail}\n"
            for fn in (f"{tid}_tool.log", "github_tool_guard.log"):
                await asyncio.to_thread(
                    lambda p=self.log_dir / fn: p.open("a", encoding="utf-8").write(entry))
        except Exception as e:
            logger.warning(f"GithubToolGuard 로그 실패: {e}")

    def _get_thread_id(self, runtime) -> str:
        try:
            config = getattr(runtime, "config", {})
            tid = config.get("configurable", {}).get("thread_id")
            if tid:
                return str(tid)
        except Exception:
            pass
        return f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
