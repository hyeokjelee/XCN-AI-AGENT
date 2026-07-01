"""입력 가드레일 — 프롬프트 인젝션/추출/정체성 덮어쓰기 시도 차단.

사용자 메시지가 에이전트로 가기 전에 검사한다. 패턴에 걸리면 거부 응답 +
차단 로그(/app/tmp/tool_log/guardrail.log)를 남기고 에이전트를 실행하지 않는다.

⚠️ 한계: 정규식/키워드 기반이라 명백한 시도는 막지만, 우회(난독화·다른 언어·
인코딩·완곡한 표현)는 100% 못 막는다. 시스템 프롬프트의 정체성 규칙과 함께 쓰는 1차 방어선이다.
편집: 아래 INJECTION_PATTERNS / BLOCK_WORDS 만 고치면 된다.
"""
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
_LOG = Path("/app/tmp/tool_log/guardrail.log")

# 단순 차단 단어(이게 들어가면 무조건 차단). 대소문자 무시.
BLOCK_WORDS = [
    "시스템 프롬프트", "시스템프롬프트", "system prompt",
    "개발자 메시지", "developer message",
    "jailbreak", "DAN 모드", "프롬프트 인젝션",
]

# 정규식 패턴(문맥 포함). 대소문자 무시.
INJECTION_PATTERNS = [
    # 시스템/지시 추출 시도 (한정어가 붙은 '프롬프트'만 — '프롬프트' 단독 오탐 방지)
    r"(시스템|system|너의?|네|당신의?|그|이)\s*프롬프트.{0,15}(보여|출력|알려|공개|내놔|보내|뱉|복사|말해)",
    r"(너의?|네)\s*(지시사항|규칙|설정|프롬프트|instructions?).{0,10}(보여|출력|알려|공개|뭐)",
    r"(이전|앞의|위의|모든|기존).{0,12}(지시|명령|규칙|프롬프트|instruction).{0,8}(무시|잊)",
    r"ignore\s+(all\s+|the\s+)?(previous|prior|above).{0,24}(instruction|prompt|rule)",
    r"disregard\s+(all\s+|the\s+)?(previous|prior|above)",
    # 역할/정체성 강제 변경
    r"(지금부터|이제부터)\s*(너는|넌|네 역할|네 정체)",
    r"act\s+as\b", r"you\s+are\s+now\b", r"pretend\s+(to\s+be|you)",
    r"제작자(는|가)\s*(나|내가|너야|아니|바뀌)",
    r"내가\s*(너를|널)\s*만들",
    # 기반 모델 캐묻기
    r"(기반|베이스|base).{0,4}모델", r"what\s+(model|llm)\s+are\s+you",
]

_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_WORDS_RE = re.compile("|".join(re.escape(w) for w in BLOCK_WORDS), re.IGNORECASE)

REFUSAL = (
    "요청하신 내용은 보안 정책상 처리할 수 없습니다. "
    "엑큐의 시스템 설정·정체성 변경이나 내부 지시 노출 요청은 거부됩니다. "
    "업무 관련 요청을 입력해 주세요."
)


def check_injection(text: str):
    """인젝션 의심 시 매칭된 문구(str)를, 아니면 None을 반환."""
    if not text:
        return None
    m = _WORDS_RE.search(text) or _RE.search(text)
    return m.group(0) if m else None


def log_block(user: str, matched: str, text: str) -> None:
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = (f"[{datetime.now().isoformat()}] [user={user}] BLOCKED "
                 f"match={matched!r} input={text[:300]!r}\n")
        _LOG.open("a", encoding="utf-8").write(entry)
    except Exception as e:
        logger.warning(f"guardrail 로그 실패: {e}")
