from middleware.summary_memory import summarization_middleware, make_memory_middleware
from deepagents import SubAgent  
from llm_conn.model import llm_model, sub_model
from pathlib import Path
from middleware.tool_logging import ToolLoggingMiddleware
from langchain_quickjs import CodeInterpreterMiddleware

async def get_coder_subagent():
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")
    prompt_content = Path("/app/sub_agents/coder/agent_compact.md").read_text()
    coder_analyst_subagent = SubAgent(
        name="code_subagent",
        description="코드 생성을 전문으로 하는 에이전트",
        system_prompt=prompt_content,
        # coder는 추론품질이 중요 → thinking 유지된 llm_model 사용(타 서브는 thinking-off sub_model)
        model=llm_model,
        # CodeInterpreterMiddleware: 코드 실행/검증(JS 샌드박스) 능력 부여
        middleware=[tool_logging_middleware, summarization_middleware, CodeInterpreterMiddleware(), make_memory_middleware("/app/sub_agents/coder/memory.md")]
    )
    return coder_analyst_subagent