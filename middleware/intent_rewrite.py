"""사용자 의도 정규화 미들웨어 (마스터 진입 전 1회).

마스터 에이전트가 사용자 턴을 처리하기 직전(`abefore_agent`)에, 방금 들어온
사용자 메시지를 경량 LLM으로 한 번 해석해 '정규화된 의도 노트'를 덧붙인다.
- 원문은 그대로 보존하고, 보조 해석을 SystemMessage로 추가(원문 우선).
- 사실(날짜·이름·수치 등)을 새로 지어내지 않고, 모호한 요청의 의도/범위만 명확화.
- LLM 호출 실패·빈 결과 등은 조용히 무시(턴을 깨지 않음).
"""
import logging
import time
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from llm_conn.model import sub_model

logger = logging.getLogger(__name__)

_LOG_PATH = Path("/app/tmp/tool_log/intent_rewrite.log")

# 너무 짧거나 명령형(slash)·인사 등은 굳이 재해석하지 않는다(불필요한 호출·왜곡 방지).
_MIN_LEN = 6
# 참조 해소용 맥락: 현재 요청 직전의 대화(질문+답변) 최근 N개.
_CTX_MSGS = 3
# 맥락 메시지 1개당 글자 상한(긴 답변이 토큰을 잠식하지 않도록 잘라서 넣음).
_CTX_MSG_MAXLEN = 600

_SYS_PROMPT = (
    "너는 멀티에이전트 오케스트레이터 '엑큐'의 입력 전처리기다. 사용자의 짧은 요청을 받아, "
    "엑큐가 **곧바로 계획(작업 분해·위임)을 세울 수 있도록** 의도를 구조화해 출력한다. "
    "요청을 직접 수행하거나 답하지 마라.\n\n"
    "아래 항목을 각각 1~2줄로, 한국어로 간결하게 작성한다(해당 없으면 그 줄 생략):\n"
    "- 목표: 사용자가 최종적으로 원하는 결과(완료 상태)를 한 줄로.\n"
    "- 대상/도메인: 다루는 데이터·자료의 성격을 분류한다 — 사내문서·규정(지식) / DB·로그(이벤트·통계) / "
    "웹 자료 / 문서 생성물(PDF·PPTX·XLSX·DOCX) / 코드 / Slack / Notion / GitHub / 시간·일정 중 가까운 것.\n"
    "- 명시된 조건: 원문에 실제로 적힌 파라미터(기간·대상·수치 등)만 적는다.\n"
    "- 도구로 확정할 값: 비어 있지만 도구·기본값으로 정할 수 있는 항목(예: '어제'의 실제 날짜, 인덱스명, "
    "필드 타입). **'사용자에게 물어볼 것'이 아니라 '실행 중 도구로 확정할 것'으로 표기한다.**\n\n"
    "규칙:\n"
    "1. 원문에 없는 사실(날짜·이름·수치·인덱스명)을 지어내지 마라. '어제'·'지난달' 같은 상대표현은 "
    "그대로 두고 '도구로 확정할 값'에 넣는다.\n"
    "2. 전담 에이전트 이름을 지정하지 마라(라우팅은 엑큐가 한다). 도메인 성격만 분류한다.\n"
    "3. 군더더기·메타설명 없이 위 항목만 출력한다. 추측으로 범위를 임의로 넓히지 마라.\n"
    "4. '[이전 대화]'(질문·답변)가 함께 주어지면, '그거·아까·그럼' 같은 지시·후속 표현을 해소하는 "
    "용도로만 참고한다. 구조화 대상은 '[현재 요청]' 하나뿐이며, 이전 대화를 다시 처리하지 마라. "
    "맥락으로 참조가 풀리면 '명시된 조건'으로 반영한다.\n"
    "5. 모호한 점·추정·되물을 거리는 출력하지 마라. 확실히 드러난 정보만 위 항목에 담는다."
)


def _text_of(content) -> str:
    """HumanMessage content를 문자열로 정규화(멀티모달 list 대응)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _log(orig: str, clarified: str) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] ORIG: {orig!r}\n[{ts}] INTENT: {clarified!r}\n")
    except Exception:
        pass


class IntentRewriteMiddleware(AgentMiddleware):
    """마스터 진입 전 사용자 의도를 정규화해 노트로 덧붙인다."""

    async def abefore_agent(self, state, runtime):
        try:
            msgs = state.get("messages") or []
            # 현재 요청 = 마지막 HumanMessage
            cur_idx = next((i for i in range(len(msgs) - 1, -1, -1)
                            if isinstance(msgs[i], HumanMessage)), None)
            if cur_idx is None:
                return None
            text = _text_of(msgs[cur_idx].content).strip()
            if len(text) < _MIN_LEN or text.startswith("/"):
                return None

            # 맥락: 현재 요청 이전의 대화(질문·답변) 최근 _CTX_MSGS개.
            # AIMessage 중 도구호출용(빈 텍스트/tool_calls)은 제외하고 실제 답변만.
            convo = []
            for m in msgs[:cur_idx]:
                if isinstance(m, HumanMessage):
                    role = "사용자"
                elif isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                    role = "어시스턴트"
                else:
                    continue
                t = _text_of(m.content).strip()
                if t:
                    convo.append((role, t[:_CTX_MSG_MAXLEN]))
            convo = convo[-_CTX_MSGS:]

            if convo:
                ctx = "\n".join(f"- {role}: {t}" for role, t in convo)
                user_content = (
                    "[이전 대화 — 맥락용(오래된→최신), 참조 해소에만 사용]\n"
                    f"{ctx}\n\n[현재 요청 — 이것만 구조화한다]\n{text}"
                )
            else:
                user_content = text

            resp = await sub_model.ainvoke(
                [SystemMessage(content=_SYS_PROMPT), HumanMessage(content=user_content)]
            )
            clarified = _text_of(getattr(resp, "content", "")).strip()
            if not clarified or clarified == text:
                return None

            _log(text, clarified)
            note = (
                "[의도 분석 — 계획 보조]\n"
                "아래는 직전 사용자 요청을 계획 수립용으로 구조화한 보조 해석이다. "
                "이를 참고해 목표·범위·작업분해를 잡되, '도구로 확정할 값'은 사용자에게 되묻지 말고 "
                "도구로 해결한다(핵심규칙 1). 원문이 우선이며, 충돌 시 원문을 따른다.\n\n"
                f"{clarified}"
            )
            return {"messages": [SystemMessage(content=note)]}
        except Exception as e:  # LLM 실패 등은 턴을 깨지 않는다.
            logger.warning(f"intent rewrite skipped: {e}")
            return None


# 메인 에이전트에서 바로 쓰도록 인스턴스 제공.
intent_rewrite_middleware = IntentRewriteMiddleware()
