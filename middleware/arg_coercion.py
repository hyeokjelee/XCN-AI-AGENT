"""인자 교정 미들웨어 — 로컬 모델이 list/dict 타입 인자를 JSON '문자열'로 직렬화해
보내는 버릇 때문에 도구가 스키마 에러로 무한 루프하는 것을 막는다.

관찰된 사례:
  write_todos(todos='[{"content":..,"status":..}]')   ← todos 가 문자열(원래 list)
  → 스키마 불일치 "Error invoking tool 'write_todos'" → 모델이 같은 형식으로 재시도
  → 2초마다 동일 호출 무한 반복(실측 166회).

여기서 todos 를 list 로 복원하면 호출이 '성공'해 루프가 풀리고, 작업이 진행되어
사용자가 결과를 본다(=죽이지 않고 고쳐서 끊는 방식). ES 의 query_body 문자열화는
es_query_guard 가 이미 같은 방식으로 처리하므로 여기선 제외한다.

확장: STRUCTURED_PARAMS 에 (도구 → 파라미터) 를 추가하면 다른 도구도 같은 보호를 받는다.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware

logger = logging.getLogger(__name__)

# 도구명 → '문자열이면 JSON 객체로 복원할' 파라미터 집합. (도구명은 github_ 등 prefix 제거 후 매칭)
# 값 타입이 항상 list/dict 인 파라미터만 넣는다(문자열이 정상인 파라미터는 넣지 말 것).
STRUCTURED_PARAMS = {
    "write_todos": {"todos"},
}


def _coerce_json(val):
    """val 이 문자열이고 JSON list/dict 로 파싱되면 그 객체를 반환, 아니면 None(변경없음)."""
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s or s[0] not in "[{":
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    return obj if isinstance(obj, (list, dict)) else None


class ArgCoercionMiddleware(AgentMiddleware):
    def __init__(self, log_dir: str = "/app/tmp/tool_log"):
        self.log_dir = Path(log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call.get("name", "")
        params = STRUCTURED_PARAMS.get(name) or STRUCTURED_PARAMS.get(name.removeprefix("github_"))
        if params:
            args = request.tool_call.get("args") or {}
            changed = []
            for p in params:
                if p in args:
                    obj = _coerce_json(args[p])
                    if obj is not None:
                        args[p] = obj
                        changed.append(p)
            if changed:
                request.tool_call["args"] = args
                self._log(request, name, changed)
        return await handler(request)

    def _log(self, request, name, changed):
        try:
            cfg = getattr(getattr(request, "runtime", None), "config", {}) or {}
            tid = cfg.get("configurable", {}).get("thread_id", "unknown")
            ts = datetime.now().isoformat()
            entry = f"[{ts}] [thread={tid}] ARG_COERCED ({name}) params={changed} (JSON문자열→객체)\n"
            for fn in (f"{tid}_tool.log", "arg_coercion.log"):
                (self.log_dir / fn).open("a", encoding="utf-8").write(entry)
        except Exception as e:
            logger.warning(f"ArgCoercion 로그 실패: {e}")
