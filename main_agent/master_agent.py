from deepagents import create_deep_agent, register_harness_profile  
from pathlib import Path  
from langgraph.store.memory import InMemoryStore
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver 
from deepagents.backends import CompositeBackend, FilesystemBackend, LocalShellBackend
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools
from langchain_quickjs import CodeInterpreterMiddleware  
from llm_conn.model import llm_model
from deepagents.profiles.harness import HarnessProfile 
from deepagents.middleware.summarization import SummarizationMiddleware  
from deepagents.middleware.memory import MemoryMiddleware
from sub_agents.search.agent import get_search_subagent
from sub_agents.coder.agent import get_coder_subagent
from sub_agents.elasticsearch.agent import get_elasticsearch_subagent
from sub_agents.slack.agent import get_slack_subagent
from sub_agents.design.agent import get_design_subagent
from sub_agents.document.agent import get_docu_subagent
from sub_agents.notion.agent import get_notion_subagent
from sub_agents.github.agent import get_github_subagent
from sub_agents.chroma.agent import get_chroma_subagent
from middleware.tool_logging import ToolLoggingMiddleware
#from middleware.master_delegation_guard import MasterDelegationGuardMiddleware
from middleware.arg_coercion import ArgCoercionMiddleware
from middleware.summary_memory import summarization_middleware, memory_middleware
from middleware.intent_rewrite import intent_rewrite_middleware  # 의도 정규화(현재 요청만 초점, 무관한 이전 맥락 차단)
import asyncio, tempfile, aiosqlite

master_agent = None

base_dir = "/app/tmp" 
tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")
#master_delegation_guard = MasterDelegationGuardMiddleware(log_dir="/app/tmp/tool_log")
arg_coercion_middleware = ArgCoercionMiddleware(log_dir="/app/tmp/tool_log")

composite_backend = CompositeBackend(  
    default=LocalShellBackend(root_dir=base_dir, virtual_mode=False),  
    routes={  
        "/tmp/": FilesystemBackend(  
            root_dir="/app/tmp/workspace",  
            virtual_mode=False  
        ),  
    },    
    artifacts_root="/app/tmp/workspace"  
)  

register_harness_profile(
    "openai",  # 또는 "openai:xcn_llm"
    HarnessProfile(
        # fs/shell 빌트인 툴 제외를 해제 → coder(code_subagent)가 read/write/edit/execute 등을
        # 실제로 사용할 수 있게 한다. 이 프로파일은 master·sub 공통(둘 다 model_provider="openai")이라
        # master도 fs 툴을 보유하게 되지만, master는 xcu-master.md의 "직접 도구 사용 금지·위임만"
        # 원칙으로 행동이 제어된다. (추후 per-agent 프로파일 분리 가능)
        excluded_tools=frozenset(),
        # class-form exclusion: exact-type 매칭이라 자동 추가되는 기본 요약기
        # (_DeepAgentsSummarizationMiddleware == SummarizationMiddleware, 기본 170k 트리거)만
        # 제거되고, 우리가 넣는 XcuSummarizationMiddleware(서브클래스, 40k/20k)는 보존된다.
        # (문자열 "SummarizationMiddleware" 로 빼면 같은 이름이라 커스텀까지 제거되어 요약이 꺼졌음)
        excluded_middleware=[SummarizationMiddleware]
    )
)  

async def init_master_agent(db_conn: aiosqlite.Connection):
    global master_agent

    checkpointer = AsyncSqliteSaver(db_conn)
    await checkpointer.setup()

    store = InMemoryStore()
    node_cache = InMemoryCache()

    # 시간 조회는 stateless·단순 1회성 작업이라 서브에이전트(LLM 왕복 추가) 대신
    # 시간 MCP 툴을 마스터 에이전트에 직접 부여한다.
    time_tools, _, _ = await resolve_and_load_mcp_tools(
        explicit_config_path="/app/main_agent/time_mcp.json",
        stateless=True,
    )

    sub_agents_list = await asyncio.gather(
        get_search_subagent(),
        get_coder_subagent(),
        get_slack_subagent(),
        get_design_subagent(),
        get_elasticsearch_subagent(),
        get_docu_subagent(),
        get_notion_subagent(),
        get_github_subagent(),
        get_chroma_subagent()
    )

    prompt_path = Path("/app/main_agent/xcu-master.md")
    prompt_content = prompt_path.read_text()

    master_agent = create_deep_agent(      
        system_prompt=prompt_content,    
        checkpointer=checkpointer,  
        store=store,  
        memory=None,      
        cache=node_cache,       
        model=llm_model,
        backend=composite_backend,
        tools=time_tools,
        subagents=list(sub_agents_list),
        middleware=[arg_coercion_middleware, tool_logging_middleware, summarization_middleware, memory_middleware]
    )

    return master_agent