from middleware.summary_memory import summarization_middleware, make_memory_middleware
from pathlib import Path
from deepagents import SubAgent 
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools 
from llm_conn.model import sub_model
from middleware.tool_logging import ToolLoggingMiddleware
from middleware.github_tool_guard import GithubToolGuardMiddleware
from sub_agents.github.git_bulk_push import make_git_bulk_push_tool, make_cleanup_tool

# tool-overload 방지: github MCP 서버는 44개 도구를 노출하는데, 로컬 모델이
# 그만큼 많은 도구 스키마에 압도되면 tool_call을 생성하지 못하고 예고 문장만 내고
# 종료한다(→ 마스터가 빈손 결과를 받고 반복 재호출). 실제 사용하는 도구만 남긴다.
# 핵심 용도: 조직 레포 생성 · 커밋/푸시 · PR 생성/관리 · 기존 레포 꾸미기(파일 편집).
GITHUB_ALLOWED_TOOLS = {
    "get_me",
    "search_repositories", "get_file_contents",
    "create_repository", "create_branch", "list_branches", "list_commits",
    "create_or_update_file", "delete_file",
    "create_pull_request", "pull_request_read", "list_pull_requests",
    "update_pull_request", "merge_pull_request",
}


async def get_github_subagent():
    print('github_mcp tool load...')
    github_tools, _, _ = await resolve_and_load_mcp_tools(
    explicit_config_path="/app/sub_agents/github/mcp.json",
    stateless=True,
    )
    # 화이트리스트 도구만 남긴다(공식 서버의 github_ prefix만 정규화).
    github_tools = [t for t in github_tools
                    if t.name in GITHUB_ALLOWED_TOOLS or t.name.removeprefix("github_") in GITHUB_ALLOWED_TOOLS]
    # 대량/폴더 단위 푸시용 결정론적 도구 + 외부 가져온 임시폴더 정리 도구 추가.
    github_tools.append(make_git_bulk_push_tool())
    github_tools.append(make_cleanup_tool())
    print(f'github_mcp tool load complete! ({len(github_tools)} tools, git_bulk_push·cleanup_fetched_path 포함)')

    prompt_content = Path("/app/sub_agents/github/agent_compact.md").read_text()
    github_guard_middleware = GithubToolGuardMiddleware(log_dir="/app/tmp/tool_log")
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")

    github_subagent = SubAgent(  
    name="github_subagent",  
    description="github MCP Server를 사용하여 레퍼지토리 조회, 수정 및 콘텐츠 관리를 수행하는 github 전문 에이전트.",  
    system_prompt=prompt_content,
    model=sub_model, 
    tools = github_tools,
    middleware=[github_guard_middleware, tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/github/memory.md")]
    )

    return github_subagent
