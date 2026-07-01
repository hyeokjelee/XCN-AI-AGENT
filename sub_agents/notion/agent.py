from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent 
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools 
from llm_conn.model import sub_model
from middleware.tool_logging import ToolLoggingMiddleware

async def get_notion_subagent():
    print('notion_mcp tool load...')
    notion_tools, _, _ = await resolve_and_load_mcp_tools(  
    explicit_config_path="/app/sub_agents/notion/mcp.json",  
    stateless=True,  
    )  
    print('notion_mcp tool load complete!')
    prompt_content = Path("/app/sub_agents/notion/agent_compact.md").read_text()
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")

    notion_subagent = SubAgent(  
    name="notion_subagent",  
    description="Notion MCP Server를 사용하여 페이지 생성, 조회, 수정 및 콘텐츠 관리를 수행하는 Notion 문서 관리 전문 에이전트.",  
    system_prompt=prompt_content,    
    model=sub_model, 
    tools = notion_tools,
    middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/notion/memory.md")]
    )

    return notion_subagent