from middleware.summary_memory import summarization_middleware, make_memory_middleware
from deepagents import SubAgent  
from llm_conn.model import llm_model, sub_model
from middleware.tool_logging import ToolLoggingMiddleware
from pathlib import Path

async def get_docu_subagent():
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")
    prompt_content = Path("/app/sub_agents/document/agent_compact.md").read_text()
    docu_subagent = SubAgent(  
        name="document_subagent",  
        description="DOCX, PDF, PPTX, XLSX 파일의 읽기·분석·생성·변환을 담당하는 문서 처리 전문 에이전트.",  
        system_prompt=prompt_content,
        skills = ['/app/sub_agents/document/pptx','/app/sub_agents/document/pdf','/app/sub_agents/document/docx','/app/sub_agents/document/xlsx'],   
        model=sub_model,  
        middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/document/memory.md")]
    )
    return docu_subagent