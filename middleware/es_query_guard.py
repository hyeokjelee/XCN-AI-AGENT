"""Elasticsearch 쿼리 자동 교정 + 반복 호출 차단 미들웨어.

로컬 LLM이 자주 내는 결정론적 오류를 도구 호출 직전에 코드로 바로잡고,
같은 쿼리를 짧은 시간에 반복 호출하는 무한루프를 끊는다.

[교정]
1) query_body 문자열 직렬화 → 객체 복원(이중 인코딩 포함)
2) size/_source/sort/aggs 등 루트 키를 query 안에 잘못 넣음 → 루트로 끌어올림
3) text 필드를 term/terms/sort에 직접 사용 → 매핑상 keyword 경로로 치환
4) 숫자 필드(pi_total 등)에 텍스트로 match/term(확정 400) → 해당 절 제거

[반복 차단]
같은 (thread, index, query_body)가 WINDOW 내에 반복되면:
- 2번째: ES 재조회 없이 직전 결과(캐시) 반환
- STOP_AT 이상: "재실행 금지" 안내 메시지를 반환해 루프를 끊음
교정/차단이 일어나면 tool_log에 기록.
"""
import asyncio
import copy
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

try:
    from json_repair import repair_json
except Exception:
    repair_json = None

logger = logging.getLogger(__name__)


def _lenient_loads(s):
    """깨진 JSON 문자열을 json-repair로 복구해 dict로 반환(실패 시 None)."""
    if repair_json is None:
        return None
    try:
        obj = repair_json(s, return_objects=True)
        return obj if isinstance(obj, dict) and obj else None
    except Exception:
        return None

SEARCH_TOOL = "elasticsearch_search"

ROOT_KEYS = {
    "size", "_source", "sort", "aggs", "aggregations", "from",
    "track_total_hits", "collapse", "highlight", "post_filter", "search_after",
}

# text 필드(base) → term/정렬/집계용 실제 keyword 경로 (매핑 검증).
# base 텍스트 필드는 자체 keyword가 없고 별도 _str 필드가 keyword라 그 경로를 매핑.
# sname(발신자명)==name 값이며 keyword는 name_str.keyword. 이메일 기준은 sender_str.
TEXT_TO_KEYWORD = {
    # base text 필드 → keyword 경로
    "subject": "subject_str.keyword",
    "sname": "name_str.keyword",
    "sender": "sender_str",
    "recvs_name": "recvs_name_str.keyword",
    "attachname": "attachname_str",
    "host": "host_str",
    "name": "name_str.keyword",
    "bname": "bname_str.keyword",
    "cname": "cname_str.keyword",
    "tname": "tname_str.keyword",
    "org_sender": "org_sender.keyword",
    "user": "user_str",
    "email": "email.keyword",
    # text 타입 _str 필드를 .keyword 없이 집계/정렬한 경우 → .keyword 보정
    # (sender_str·attachname_str·host_str·user_str·body_snippet 은 keyword라 직접 가능 → 제외)
    "name_str": "name_str.keyword",
    "recvs_name_str": "recvs_name_str.keyword",
    "subject_str": "subject_str.keyword",
    "bname_str": "bname_str.keyword",
    "cname_str": "cname_str.keyword",
    "tname_str": "tname_str.keyword",
    "cc_str": "cc_str.keyword",
    "bcc_str": "bcc_str.keyword",
    "org_sender_str": "org_sender_str.keyword",
}

# 집계/정렬에 _id 사용 금지(fielddata 막힘 → 400). 모든 문서에 존재하는 keyword로 치환.
# value_count(_id)=문서 수 ↔ value_count(ctime)=문서 수 로 결과 동일.
SAFE_AGG_FIELD = "ctime"

# 숫자(long/integer) 필드 — 사람 이름·텍스트로 match/term 하면 number_format_exception → 400.
# (예: {"match": {"pi_total": "민기"}}) 의미상 필드 오선택이므로 해당 절을 제거해 400을 막는다.
# 올바른 이름 검색은 sname(match)/name_str.keyword(term)이며 프롬프트(§0)가 안내한다.
_NUMERIC_FIELDS = {"pi_total", "attachcnt", "attachsize", "attachsizesum"}

# 반복 차단 파라미터
_WINDOW = 90.0     # 초: 이 시간 내 동일 쿼리만 '반복'으로 본다
_STOP_AT = 3       # 동일 쿼리 N번째부터 중단 메시지
_MAX_KEYS = 1000   # 카운터 dict 상한


class ESQueryGuardMiddleware(AgentMiddleware):
    def __init__(self, log_dir: str = "/app/tmp/tool_log"):
        self.log_dir = Path(log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._repeat: dict = {}  # key -> {ts0, count, content}

    async def awrap_tool_call(self, request, handler):
        if request.tool_call.get("name") != SEARCH_TOOL:
            return await handler(request)

        # 1) 정규화/교정
        args = request.tool_call.get("args") or {}
        if "query_body" in args:
            try:
                norm = self._normalize(args["query_body"])
                if norm is not None:
                    if self._is_changed(args["query_body"], norm):
                        await self._log_correction(request, args["query_body"], norm)
                    args["query_body"] = norm
                    request.tool_call["args"] = args
            except Exception as e:
                logger.warning(f"ESQueryGuard 정규화 건너뜀: {e}")

        # 2) 반복 차단
        try:
            decision = self._repeat_check(request, args)
            if decision is not None:
                return decision
        except Exception as e:
            logger.warning(f"ESQueryGuard 반복체크 건너뜀: {e}")

        # 2.3) query_body 누락/빈값 → MCP 가 'missing field query_body'로 작업을 abort 시킨다.
        #      실행 전에 잡아 되튕겨(재시도 유도), 전체 중단을 막는다.
        qb0 = args.get("query_body")
        if "query_body" not in args or qb0 is None or (isinstance(qb0, (str, dict, list)) and len(qb0) == 0):
            await self._log_error_bounce(request, "missing query_body")
            return ToolMessage(
                content=("[가드] `query_body` 가 빠졌습니다. elasticsearch_search 는 `index` 와 "
                         "`query_body` 를 **둘 다** 채워야 합니다. 같은 호출을 반복하지 말고 query_body 를 "
                         '채워 다시 시도하세요. 예: {"index":"edc_w_202606","query_body":{"size":50,'
                         '"_source":["sname","subject","ctime"],"query":{"bool":{"must":[{"match":{"sname":"이름"}}],'
                         '"filter":[{"range":{"ctime":{"gte":"20260601000000","lte":"20260630235959"}}}]}}}}'),
                tool_call_id=request.tool_call.get("id", ""), name=SEARCH_TOOL)

        # 2.5) 정리 결과 '조건이 비어버린' 미완성 쿼리는 match_all 실행(쓰레기 50건) 대신 되튕긴다.
        #      (skeleton/빈값 절을 다 쳐내 must/should/filter 가 전부 빈 bool. aggs 있으면 전체집계라 통과)
        try:
            qb = args.get("query_body")
            if isinstance(qb, dict) and self._is_empty_bool_query(qb) \
               and not qb.get("aggs") and not qb.get("aggregations"):
                await self._log_error_bounce(request, "empty_bool_query(미완성 절만)")
                return ToolMessage(
                    content=("[가드] 쿼리에 유효한 검색 조건이 없습니다(미완성/빈 절만 있었습니다). "
                             "같은 쿼리를 반복하지 말고, 필드와 검색어를 채워 다시 시도하세요. "
                             '예: {"query":{"bool":{"must":[{"match":{"subject":"키워드"}}],'
                             '"filter":[{"range":{"ctime":{"gte":"20260601000000","lte":"20260630235959"}}}]}}}'),
                    tool_call_id=request.tool_call.get("id", ""), name=SEARCH_TOOL)
        except Exception as e:
            logger.warning(f"ESQueryGuard 빈쿼리체크 건너뜀: {e}")

        # 3) 실제 실행 — 에러(특히 ES 4xx)면 원문 대신 '교정 안내'로 되튕긴다.
        #    (raw 400 을 그대로 주면 모델이 같은 쿼리로 반복 → 루프. 안내로 바꿔 자가수정을 유도.
        #     같은 쿼리를 또 던지면 위 2)반복차단이 막는다. 추측 재실행은 '엉뚱한 결과' 위험이라 안 함.)
        try:
            result = await handler(request)
        except Exception as e:
            if self._looks_like_es_4xx(e):
                await self._log_error_bounce(request, e)
                return ToolMessage(content=self._error_guidance(e),
                                   tool_call_id=request.tool_call.get("id", ""), name=SEARCH_TOOL)
            raise
        try:
            self._cache_result(request, args, result)
        except Exception:
            pass
        return result

    # ---------- ES 실행 에러 → 교정 안내 되튕김 ----------
    @staticmethod
    def _looks_like_es_4xx(e) -> bool:
        # ES 4xx + MCP 요청형식 오류(파라미터 역직렬화/누락/검증)도 포함 — 이런 건 작업을 abort 시키지
        # 말고 '교정 안내'로 되튕겨 재시도시킨다. (5xx 서버오류는 제외 → 그대로 재전파)
        s = str(e).lower()
        return any(k in s for k in (
            "400", "bad request", "client error", "x_content", "parsing_exception",
            "illegal_argument", "number_format", "search_phase", "no mapping", "query_shard",
            "deserialize", "missing field", "missing required", "invalid params",
            "validation", "unprocessable", "422"))

    @staticmethod
    def _error_guidance(e) -> str:
        return ("[가드] 이 ES 쿼리가 거부됐습니다(아래 사유로 추정). **같은 쿼리를 반복하지 말고** "
                "한 번만 수정해 다시 시도하세요:\n"
                "① 치트시트에 없는 필드/오타 — 정의된 필드만 사용\n"
                "② 숫자필드(pi_total·attachcnt 등)에 텍스트로 match/term — 이름검색은 sname(match)\n"
                "③ phrase 계열(match_phrase·match_phrase_prefix) 사용 — text 검색은 그냥 match\n"
                "④ text 필드를 term/sort/aggs에 직접 사용 — keyword 경로(…_str.keyword)로\n"
                "수정이 애매하면 **가장 단순한 단일 match 로 좁혀** 다시 시도하세요.")

    async def _log_error_bounce(self, request, e):
        try:
            tid = self._get_thread_id(getattr(request, "runtime", None))
            ts = datetime.now().isoformat()
            entry = f"[{ts}] [thread={tid}] ES_QUERY_ERROR_BOUNCE → 교정안내 반환 ({str(e)[:120]})\n"
            for fn in (f"{tid}_tool.log", "es_query_guard.log"):
                await asyncio.to_thread(
                    lambda p=self.log_dir / fn: p.open("a", encoding="utf-8").write(entry))
        except Exception:
            pass

    # ---------- 반복 차단 ----------
    def _key(self, request, args):
        tid = self._get_thread_id(getattr(request, "runtime", None))
        try:
            q = json.dumps(args.get("query_body"), sort_keys=True, ensure_ascii=False)
        except Exception:
            q = str(args.get("query_body"))
        return (tid, str(args.get("index")), q)

    def _repeat_check(self, request, args):
        now = time.monotonic()
        if len(self._repeat) > _MAX_KEYS:  # 오래된 항목 정리
            self._repeat = {k: v for k, v in self._repeat.items() if now - v["ts0"] <= _WINDOW}
        key = self._key(request, args)
        ent = self._repeat.get(key)
        if ent is None or now - ent["ts0"] > _WINDOW:
            self._repeat[key] = {"ts0": now, "count": 1, "content": None}
            return None  # 첫 호출 → 정상 실행
        ent["count"] += 1
        tcid = request.tool_call.get("id", "")
        if ent["count"] >= _STOP_AT:
            self._log_block(request, ent["count"])
            return ToolMessage(
                content=("[중단] 직전과 동일한 쿼리를 반복 호출했습니다. 같은 쿼리를 "
                         "다시 실행하지 말고, 이미 받은 결과를 사용해 분석·보고를 완료하세요. "
                         "새로운 정보가 필요하면 '다른 필드/다른 집계'로 쿼리를 바꾸세요."),
                tool_call_id=tcid, name=SEARCH_TOOL,
            )
        if ent.get("content") is not None:
            # 동일 결과 캐시 반환 (ES 재조회 없음)
            return ToolMessage(content=ent["content"], tool_call_id=tcid, name=SEARCH_TOOL)
        return None  # 캐시 없으면 정상 실행

    def _cache_result(self, request, args, result):
        key = self._key(request, args)
        ent = self._repeat.get(key)
        if ent is not None and ent.get("content") is None:
            ent["content"] = getattr(result, "content", None)

    def _log_block(self, request, count):
        try:
            tid = self._get_thread_id(getattr(request, "runtime", None))
            ts = datetime.now().isoformat()
            entry = f"[{ts}] [thread={tid}] ES_QUERY_BLOCKED (동일 쿼리 {count}회 반복 → 중단 메시지 반환)\n"
            for fn in (f"{tid}_tool.log", "es_query_guard.log"):
                (self.log_dir / fn).open("a", encoding="utf-8").write(entry)
        except Exception:
            pass

    # ---------- 변경 여부 ----------
    def _is_changed(self, original, fixed) -> bool:
        if isinstance(original, str):
            return True
        try:
            return (json.dumps(original, sort_keys=True, ensure_ascii=False)
                    != json.dumps(fixed, sort_keys=True, ensure_ascii=False))
        except Exception:
            return original != fixed

    # ---------- 로깅 ----------
    def _get_thread_id(self, runtime) -> str:
        try:
            config = getattr(runtime, "config", {})
            tid = config.get("configurable", {}).get("thread_id")
            if tid:
                return str(tid)
        except Exception:
            pass
        return f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _log_correction(self, request, original, fixed):
        try:
            thread_id = self._get_thread_id(getattr(request, "runtime", None))
            ts = datetime.now().isoformat()
            before = original if isinstance(original, str) else json.dumps(original, ensure_ascii=False)
            after = json.dumps(fixed, ensure_ascii=False)
            entry = (f"[{ts}] [thread={thread_id}] ES_QUERY_CORRECTED\n"
                     f"  BEFORE: {before}\n  AFTER : {after}\n")
            for fn in (f"{thread_id}_tool.log", "es_query_guard.log"):
                await asyncio.to_thread(
                    lambda p=self.log_dir / fn: p.open("a", encoding="utf-8").write(entry))
        except Exception as e:
            logger.warning(f"ESQueryGuard 로그 실패: {e}")

    # ---------- 정규화 ----------
    def _normalize(self, qb):
        for _ in range(2):
            if isinstance(qb, str):
                try:
                    qb = json.loads(qb)
                except Exception:
                    # 깨진 JSON 문자열 → json-repair로 복구 시도
                    repaired = _lenient_loads(qb)
                    if not isinstance(repaired, dict):
                        return None
                    qb = repaired
                    break
            else:
                break
        if not isinstance(qb, dict):
            return None
        qb = copy.deepcopy(qb)
        q = qb.get("query")
        if isinstance(q, dict):
            for k in list(q.keys()):
                if k in ROOT_KEYS:
                    qb.setdefault(k, q.pop(k))
            if not q:
                qb.pop("query", None)
        self._fix_fields(qb)
        self._fix_phrase_ops(qb)
        self._prune_invalid_clauses(qb)
        self._sanitize_aggs(qb)
        self._prune_numeric_text(qb)
        # 최상위 query 자체가 잘못된 숫자-텍스트 절이면 제거(→ match_all). bool 안의 절은 _prune에서 처리.
        if self._is_bad_numeric_clause(qb.get("query")):
            qb.pop("query", None)
        self._fix_agg_order(qb)
        return qb

    # ---------- 미완성/무효 절 제거 ----------
    # 모델이 bool 절 배열에 검색어를 못 채운 placeholder(예: ['..._placeholder_for_rag'])나
    # 비-dict(문자열·리스트), 빈 dict 를 그대로 넣어 400 을 내는 경우가 있다 → 유효 절만 남긴다.
    _PLACEHOLDER_MARKERS = ("placeholder", "fill_me", "fillme", "to_be_filled", "${", "todo_query")

    def _has_placeholder(self, node) -> bool:
        if isinstance(node, str):
            low = node.lower()
            if any(m in low for m in self._PLACEHOLDER_MARKERS):
                return True
            s = node.strip()
            return len(s) >= 2 and s[0] == "<" and s[-1] == ">"   # <검색어> 류 미치환 템플릿
        if isinstance(node, dict):
            return any(self._has_placeholder(k) or self._has_placeholder(v) for k, v in node.items())
        if isinstance(node, list):
            return any(self._has_placeholder(x) for x in node)
        return False

    _LEAF_OPS = {"match", "match_phrase", "match_phrase_prefix", "match_bool_prefix",
                 "term", "terms", "prefix", "wildcard", "regexp", "fuzzy"}
    _COMPOUND_OPS = {"bool", "nested", "dis_max", "constant_score", "function_score", "boosting"}

    @staticmethod
    def _blank(v) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict)):
            return len(v) == 0
        return False

    def _clause_bad(self, c) -> bool:
        """절(쿼리 dict 하나)이 비었거나/빈 검색어/형식오류면 True(=제거 대상).
        예) {match:{subject_str:''}}(빈값) · {range:['ctime.gte']}(list body) · {range:{ctime:{gte:''}}}(빈 경계)."""
        if not isinstance(c, dict) or not c:
            return True
        for op, body in c.items():
            if op in self._COMPOUND_OPS:
                return False                                  # 복합 절은 유효(하위는 재귀 처리)
            if op == "range":
                if not isinstance(body, dict) or not body:
                    return True                               # range:[...] 또는 range:{} → 형식오류
                for _f, bounds in body.items():
                    if not isinstance(bounds, dict) or not any(not self._blank(v) for v in bounds.values()):
                        return True                           # 경계가 dict 아님 / 모두 빈 값
                return False
            if op in self._LEAF_OPS:
                if not isinstance(body, dict) or not body:
                    return True
                for _f, val in body.items():
                    v = val.get("query", val.get("value", "")) if isinstance(val, dict) else val
                    if self._blank(v):
                        return True                           # 검색어가 빈 값
                return False
            # 모르는 op(exists 등)은 통과
        return False

    def _is_valid_clause(self, c) -> bool:
        # 유효한 bool 하위 절: 비어있지 않은 dict · placeholder 없음 · 빈값/형식오류 아님.
        return (isinstance(c, dict) and len(c) > 0
                and not self._has_placeholder(c)
                and not self._clause_bad(c))

    def _sanitize_aggs(self, node):
        """aggs/aggregations 가 dict 가 아니거나(리스트·문자열) 하위 정의가 dict 가 아니면 제거한다.
        퇴화한 모델이 aggs 자리에 [긴 헛소리 문자열] 같은 걸 넣어 400 을 내는 것을 막는다."""
        if isinstance(node, dict):
            for k in ("aggs", "aggregations"):
                v = node.get(k)
                if k not in node:
                    continue
                if not isinstance(v, dict) or not v:
                    node.pop(k, None)                       # 리스트·문자열·빈 dict → 통째로 제거
                    continue
                for name in list(v.keys()):                 # 각 하위 agg 정의는 dict 여야
                    if not isinstance(v.get(name), dict) or not v.get(name):
                        v.pop(name, None)
                if not v:
                    node.pop(k, None)
                else:
                    self._sanitize_aggs(v)                  # 중첩 aggs 재귀
            for kk, vv in node.items():
                if kk not in ("aggs", "aggregations"):
                    self._sanitize_aggs(vv)
        elif isinstance(node, list):
            for it in node:
                self._sanitize_aggs(it)

    def _is_empty_bool_query(self, qb) -> bool:
        """정리 결과 query 가 'bool 인데 must/should/filter/must_not 가 전부 비었음'이면 True.
        (미완성 skeleton 을 다 쳐내 사실상 조건이 없어진 상태 → match_all 실행 대신 되튕긴다.)"""
        q = qb.get("query") if isinstance(qb, dict) else None
        if not isinstance(q, dict):
            return False
        b = q.get("bool")
        if not isinstance(b, dict):
            return False
        return not any(b.get(k) for k in ("must", "should", "filter", "must_not"))

    def _prune_invalid_clauses(self, node):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k in ("must", "should", "filter", "must_not") and isinstance(v, list):
                    kept = [c for c in v if self._is_valid_clause(c)]
                    node[k] = kept
                    for c in kept:
                        self._prune_invalid_clauses(c)
                else:
                    self._prune_invalid_clauses(v)
        elif isinstance(node, list):
            for it in node:
                self._prune_invalid_clauses(it)

    # ---------- 숫자 필드 텍스트 match/term 제거 ----------
    @staticmethod
    def _is_numeric_value(v) -> bool:
        if isinstance(v, bool):
            return False
        if isinstance(v, (int, float)):
            return True
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return False
            try:
                float(s)
                return True
            except ValueError:
                return False
        return False

    def _is_bad_numeric_clause(self, clause) -> bool:
        """{"match"|"term": {<숫자필드>: <비숫자값>}} 형태인지 판정(확정 400)."""
        if not isinstance(clause, dict) or len(clause) != 1:
            return False
        op = next(iter(clause))
        if op not in ("match", "term"):
            return False
        body = clause[op]
        if not isinstance(body, dict):
            return False
        for field, val in body.items():
            base = str(field).split(".")[0].lower()
            if base in _NUMERIC_FIELDS:
                v = val.get("value") if isinstance(val, dict) else val
                if not self._is_numeric_value(v):
                    return True
        return False

    def _prune_numeric_text(self, node):
        """bool 절 리스트(must/should/filter/must_not)에서 숫자필드 텍스트 절을 제거."""
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k in ("must", "should", "filter", "must_not") and isinstance(v, list):
                    kept = [c for c in v if not self._is_bad_numeric_clause(c)]
                    node[k] = kept
                    for c in kept:
                        self._prune_numeric_text(c)
                else:
                    self._prune_numeric_text(v)
        elif isinstance(node, list):
            for it in node:
                self._prune_numeric_text(it)

    def _fix_fields(self, node):
        if isinstance(node, dict):
            # 모든 집계/메트릭의 "field" 키 (terms·cardinality·avg·max·min·sum·histogram·date_histogram·percentiles 등)
            fld = node.get("field")
            if isinstance(fld, str):
                if fld == "_id":
                    node["field"] = SAFE_AGG_FIELD          # _id 집계 금지 → 안전 keyword
                elif fld in TEXT_TO_KEYWORD:
                    node["field"] = TEXT_TO_KEYWORD[fld]
            for key, val in list(node.items()):
                if key == "term" and isinstance(val, dict):
                    self._swap_field_keys(val)
                elif key == "terms" and isinstance(val, dict) and "field" not in val:
                    # terms 쿼리: {"terms": {"<field>": [..]}}  (terms 집계의 field는 위에서 처리)
                    self._swap_field_keys(val)
                elif key == "sort":
                    self._fix_sort(val)
                else:
                    self._fix_fields(val)
        elif isinstance(node, list):
            for item in node:
                self._fix_fields(item)

    # 검색 연산자 화이트리스트 정책: 허용 = match·multi_match·term·terms·range·exists·bool(+aggs).
    # 그 외 leaf 연산자(phrase 계열·prefix·wildcard·regexp·fuzzy)는 이 메일 인덱스에서 400을 내거나
    # 작은 모델이 자주 틀린다 → 안전하게 **일반 `match`로 강등**한다(.keyword 는 떼고, slop·max_expansions
    # 등 전용 파라미터는 버리고 검색어만 남긴다). 단일 토큰 검색엔 의미 차이도 거의 없다.
    # (term/terms/range/exists/match/multi_match/bool 은 그대로 둔다.)
    _PHRASE_OPS = {"match_phrase", "match_phrase_prefix", "match_bool_prefix",
                   "prefix", "wildcard", "regexp", "fuzzy"}

    def _fix_phrase_ops(self, node):
        if isinstance(node, dict):
            converted = {}
            for op in list(node.keys()):
                if op in self._PHRASE_OPS and isinstance(node[op], dict):
                    body = node.pop(op)
                    for fld, val in body.items():
                        if isinstance(fld, str) and fld.endswith(".keyword"):
                            fld = fld[: -len(".keyword")]          # phrase→match 시 분석형 text 사용
                        if isinstance(val, dict):                  # {query:.., slop:.., max_expansions:..}
                            val = val.get("query", val.get("value", ""))
                        converted[fld] = val
            if converted:
                m = node.get("match")
                if not isinstance(m, dict):
                    m = {}; node["match"] = m
                m.update(converted)
            for v in node.values():
                self._fix_phrase_ops(v)
        elif isinstance(node, list):
            for it in node:
                self._fix_phrase_ops(it)

    def _swap_field_keys(self, d):
        for f in list(d.keys()):
            if f in TEXT_TO_KEYWORD:
                d[TEXT_TO_KEYWORD[f]] = d.pop(f)

    def _fix_sort(self, sort):
        items = sort if isinstance(sort, list) else [sort]
        for it in items:
            if isinstance(it, dict):
                for f in list(it.keys()):
                    if f == "_id":
                        it[SAFE_AGG_FIELD] = it.pop(f)   # _id 정렬 금지 → 안전 keyword
                    elif f in TEXT_TO_KEYWORD:
                        it[TEXT_TO_KEYWORD[f]] = it.pop(f)

    # ---------- 집계 order 메트릭 위치 교정 ----------
    # terms/histogram 의 order 가 메트릭(sum/avg 등) 기준 정렬인데, 그 메트릭이
    # 같은 terms 의 하위(aggs)가 아니라 '형제'로 빠져 있으면 ES 가 order 경로를
    # 못 찾아 400(invalid aggregation order path) 이 난다 → 형제 메트릭을 하위로 이동.
    _ORDER_BUCKETS = ("terms", "histogram", "date_histogram")
    _ORDER_RESERVED = {"_count", "_key", "_term", "doc_count"}

    def _fix_agg_order(self, node):
        if isinstance(node, dict):
            for key in ("aggs", "aggregations"):
                aggs = node.get(key)
                if isinstance(aggs, dict):
                    self._relocate_order_metrics(aggs)
                    for sub in list(aggs.values()):
                        self._fix_agg_order(sub)
            for k, v in node.items():
                if k not in ("aggs", "aggregations"):
                    self._fix_agg_order(v)
        elif isinstance(node, list):
            for it in node:
                self._fix_agg_order(it)

    def _relocate_order_metrics(self, aggs):
        for name in list(aggs.keys()):
            aggdef = aggs.get(name)
            if not isinstance(aggdef, dict):
                continue
            bucket = next((aggdef[b] for b in self._ORDER_BUCKETS
                           if isinstance(aggdef.get(b), dict)), None)
            if bucket is None or "order" not in bucket:
                continue
            order_items = bucket["order"]
            as_list = isinstance(order_items, list)
            items = order_items if as_list else [order_items]
            for oi in items:
                if not isinstance(oi, dict):
                    continue
                for metric_path in list(oi.keys()):
                    base = metric_path.split(".")[0].split(">")[-1].strip()
                    if not base or base in self._ORDER_RESERVED:
                        continue
                    sub = aggdef.get("aggs") or aggdef.get("aggregations") or {}
                    if base in sub:
                        continue                      # 이미 하위에 있음(정상)
                    sibling = aggs.get(base)
                    if base != name and isinstance(sibling, dict):
                        # 형제 메트릭 → 해당 terms 의 하위 aggs 로 이동
                        aggdef.setdefault("aggs", {})[base] = aggs.pop(base)
                    else:
                        # 어디에도 없는 메트릭으로 정렬 → 유효하지 않은 order path(400).
                        # 해당 정렬 키 제거(기본 건수 정렬로 폴백).
                        oi.pop(metric_path, None)
            # 빈 order 정리: 유효 키가 하나도 안 남으면 order 제거(ES 기본=_count desc)
            cleaned = [oi for oi in items if isinstance(oi, dict) and oi]
            if not cleaned:
                bucket.pop("order", None)
            else:
                bucket["order"] = cleaned if as_list else cleaned[0]
