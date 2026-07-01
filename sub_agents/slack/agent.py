from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent 
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools 
from llm_conn.model import sub_model
from middleware.tool_logging import ToolLoggingMiddleware

async def get_slack_subagent():
    print('slack_mcp tool load...')
    slack_tools, _, _ = await resolve_and_load_mcp_tools(  
    explicit_config_path="/app/sub_agents/slack/mcp.json",  
    stateless=True,  
    )  
    print('slack_mcp tool load complete!')

    prompt_content = Path("/app/sub_agents/slack/agent_compact.md").read_text()
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")

    slack_subagent = SubAgent(  
    name="slack_subagent",  
    description="slack MCP Server를 사용하여 페이지 생성, 조회, 수정 및 콘텐츠 관리를 수행하는 slack 전문 에이전트.",  
    system_prompt=prompt_content,    
    model=sub_model, 
    tools = slack_tools,
    middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/slack/memory.md")]
    )

    return slack_subagent