from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools
from llm_conn.model import sub_model
from middleware.tool_logging import ToolLoggingMiddleware

tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")


async def get_search_subagent():
    # stateless=True : 호출마다 독립 세션(동시 사용자 충돌 방지)
    print('web_search_mcp tool load...')
    tools, _, _ = await resolve_and_load_mcp_tools(
        explicit_config_path="/app/sub_agents/search/mcp.json",
        stateless=True,
    )
    print('web_search_mcp tool complete!')
    prompt = Path("/app/sub_agents/search/agent_compact.md").read_text()
    return SubAgent(
        name="search_subagent",
        description="웹 검색·자료 수집을 전문으로 하는 에이전트(Tavily).",
        system_prompt=prompt,
        model=sub_model,
        tools=tools,
        middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/search/memory.md")],
    )
