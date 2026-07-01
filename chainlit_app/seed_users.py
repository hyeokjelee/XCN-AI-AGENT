"""관리자 계정 보장 스크립트.

- admin 계정의 비밀번호를 admin1! 로 항상 고정(보장)한다.
- admin 외 어떤 계정도 생성/수정/삭제하지 않는다.
  → 관리자가 콘솔에서 만든 사용자는 재시작해도 그대로 유지된다.

사용법:
  python seed_users.py                              # admin 계정만 보장
  python seed_users.py <id> <pw> [name] [role]      # 개별 사용자 추가/갱신(수동)
"""
import sys

from database import init_db, create_user

ADMIN_ID = "admin"
ADMIN_PW = "admin1!"
ADMIN_NAME = "관리자"


def main():
    init_db()
    if len(sys.argv) >= 3:
        # 수동 추가 모드(원할 때만 사용)
        ident, pw = sys.argv[1], sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else ident
        role = sys.argv[4] if len(sys.argv) > 4 else "user"
        create_user(ident, pw, name, role)
        print(f"created/updated user: {ident} ({role})")
    else:
        # 기본 동작: admin 계정만 admin1! 로 보장 (그 외 계정은 건드리지 않음)
        create_user(ADMIN_ID, ADMIN_PW, ADMIN_NAME, "admin")
        print(f"ensured admin account: {ADMIN_ID} (password fixed)")


if __name__ == "__main__":
    main()
