from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools
from llm_conn.model import sub_model
from middleware.tool_logging import ToolLoggingMiddleware

tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")

# 이 서브에이전트는 '사내문서 검색·답변' 전용(읽기 전용)이다.
# 컬렉션/문서를 생성·수정·삭제하는 도구는 제외하고 조회 도구만 노출한다.
# (벡터DB 적재/관리는 관리자(admin) 화면에서만 수행)
# get_collection_info·peek_collection 은 임베딩(numpy.ndarray)을 직렬화하려다
# "Unable to serialize unknown type: numpy.ndarray" 에러가 나므로 제외한다.
# (검색/답변에 불필요. 필요한 메타는 list_collections·get_collection_count 로 충분)
CHROMA_READ_ONLY_TOOLS = {
    "chroma_list_collections",
    "chroma_get_collection_count",
    "chroma_query_documents",
    "chroma_get_documents",
}


async def get_chroma_subagent():
    # stateless=True : 호출마다 독립 세션(동시 사용자 충돌 방지)
    print('chroma_mcp tool load...')
    tools, _, _ = await resolve_and_load_mcp_tools(
        explicit_config_path="/app/sub_agents/chroma/mcp.json",
        stateless=True,
    )
    # 읽기 전용 도구만 남긴다(생성/수정/삭제 도구 제외).
    tools = [t for t in tools
             if any(t.name.endswith(s) for s in CHROMA_READ_ONLY_TOOLS)]
    print(f'chroma_mcp tool complete! (read-only {len(tools)} tools)')
    prompt = Path("/app/sub_agents/chroma/agent_compact.md").read_text()
    return SubAgent(
        name="chroma_subagent",
        description="chroma MCP Server를 사용하여 사내 지식(벡터DB) 검색을 돕는 chromadb 전문 에이전트.",
        system_prompt=prompt,
        model=sub_model,
        tools=tools,
        middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/chroma/memory.md")],
    )
