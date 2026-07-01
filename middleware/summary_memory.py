"""공용 요약/메모리 미들웨어 인스턴스.

- 서브에이전트:  from middleware.summary_memory import summarization_middleware
- 메인 에이전트: from middleware.summary_memory import summarization_middleware, memory_middleware
"""
from deepagents.backends import LocalShellBackend, StateBackend
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.summarization import SummarizationMiddleware

from llm_conn.model import sub_model

# 커스텀 요약기를 별도 '서브클래스'로 둔다.
# 이유: deepagents create_deep_agent 는 각 에이전트에 기본 요약기
# (_DeepAgentsSummarizationMiddleware == SummarizationMiddleware, 기본 트리거 170k tokens)를
# 자동 추가한다. 마스터 하니스 프로파일이 base class 를 class-form 으로 exclude 하면
# (excluded_middleware=[SummarizationMiddleware]) exact-type 매칭이라 자동분만 제거되고,
# 이 서브클래스 인스턴스(40k/20k)는 보존된다. (문자열 "SummarizationMiddleware" 로 빼면
# 이름이 같아 자동분+커스텀 둘 다 제거되어 요약이 완전히 꺼졌었음 → 그 버그를 회피)
class XcuSummarizationMiddleware(SummarizationMiddleware):
    """40k/20k 커스텀 트리거 유지를 위한 별도 타입. 동작은 부모와 동일."""
    pass


# 요약: 로컬 모델 품질·컨텍스트 관리 위해 40k에서 미리 압축(자동 기본 170k는 너무 늦음)
summarization_middleware = XcuSummarizationMiddleware(
    model=sub_model,
    # backend 는 문자열이 아니라 Backend 객체여야 한다. "state"(문자열)를 넘기면 offload 시
    # "state".awrite() 호출 → AttributeError 로 매 요약마다 실패했음(히스토리 유실 + 에러 다발).
    # StateBackend()는 BackendProtocol.awrite(=self.write 위임)를 상속하므로 정상 동작하고,
    # 원래 의도(state 기반·ephemeral·파일시스템 비의존)도 그대로 유지된다.
    backend=StateBackend(),
    trigger=("tokens", 30_000),
    keep=("tokens", 15_000),
)

# 메모리: 에이전트별 memory.md 로드 + 피드백 영속화
# - 읽기: before_agent 훅이 sources의 memory.md를 매 호출 시스템 프롬프트에 주입
# - 쓰기: 에이전트가 read_file/edit_file로 직접 memory.md를 갱신 → 다음 세션에 반영
#   (/app 은 docker-compose에서 ./workspace 로 바인드 마운트 → 호스트에 영속)
_memory_backend = LocalShellBackend(root_dir="/app", virtual_mode=False)

# 에이전트가 피드백을 스스로 memory.md에 기록하도록 유도하는 지침(전 에이전트 공통).
# MemoryMiddleware.system_prompt 로 주입되므로 각 에이전트의 시스템 프롬프트에 포함된다.
# 주의: MemoryMiddleware.system_prompt 는 `{agent_memory}` 슬롯을 반드시 포함해야 한다
# (그 자리에 memory.md 누적 내용이 주입된다). 슬롯이 없으면 ValueError로 기동 실패.
_MEMORY_FEEDBACK_PROMPT = """\
## 메모리(memory.md) 사용 — 피드백 영속화
- 아래 <agent_memory>는 네 전용 memory.md의 누적 내용이다(이전 세션 포함). 항상 우선 반영한다.
- 사용자가 반복되는 선호를 보이거나 "기억해 / 다음부터는 / 항상 ~해" 처럼 명시적으로 요청하면,
  네 memory.md를 `read_file`로 읽고 `edit_file`로 해당 항목을 추가·갱신해 영속화한다.
- 재사용 가치가 있는 규칙·선호·교정만 간결히 적는다. 일시적·일회성 정보는 저장하지 않는다.

<agent_memory>
{agent_memory}
</agent_memory>
"""


def make_memory_middleware(source_path: str) -> MemoryMiddleware:
    """에이전트별 memory.md를 로드/주입하고 피드백 기록 지침을 부여하는 미들웨어."""
    return MemoryMiddleware(
        backend=_memory_backend,
        sources=[source_path],
        system_prompt=_MEMORY_FEEDBACK_PROMPT,
    )


# 메인(마스터) 전용 메모리 미들웨어 (기존 import 호환 유지)
memory_middleware = make_memory_middleware("/app/main_agent/memory.md")
