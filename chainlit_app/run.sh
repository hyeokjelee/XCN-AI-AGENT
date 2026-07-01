#!/usr/bin/env bash
# XCU Chainlit 앱 실행 스크립트 (xcu 컨테이너 내부에서 실행)
set -e
export PYTHONPATH=/app
cd /app/chainlit_app
# 최초 1회 기본 사용자 시드(이미 있으면 갱신)
python seed_users.py >/dev/null 2>&1 || true
exec chainlit run app.py --host 0.0.0.0 --port "${CHAINLIT_PORT:-8001}"
