from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools 
from llm_conn.model import sub_model, llm_model
from middleware.tool_logging import ToolLoggingMiddleware
from middleware.es_query_guard import ESQueryGuardMiddleware

tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")
es_query_guard_middleware = ESQueryGuardMiddleware()

async def get_elasticsearch_subagent():
    print('elasticsearch_mcp tool load...')
    elasticsearch_tools, _, _ = await resolve_and_load_mcp_tools(  
    explicit_config_path="/app/sub_agents/elasticsearch/mcp.json",  
    stateless=True,  
    )  
    tools_to_exclude = ["elasticsearch_get_mappings","elasticsearch_esql"] 
    filtered_tools = [tool for tool in elasticsearch_tools if tool.name not in tools_to_exclude]
    print('elasticsearch_mcp tool load complete!')
    prompt_content = Path("/app/sub_agents/elasticsearch/agent_compact.md").read_text()
    elasticsearch_subagent = SubAgent(  
    name="elasticsearch_subagent",  
    description="elasticsearch에서 데이터 조회, 집계등 정보수집을 전문으로 하는 에이전트",  
    system_prompt=prompt_content,    
    model=llm_model, 
    tools = filtered_tools,
    middleware=[
        es_query_guard_middleware, 
        tool_logging_middleware, 
        summarization_middleware, 
        make_memory_middleware("/app/sub_agents/elasticsearch/memory.md")
        ]
    )

    return elasticsearch_subagent