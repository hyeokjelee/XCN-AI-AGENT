from middleware.summary_memory import summarization_middleware, make_memory_middleware
from deepagents import SubAgent  
from llm_conn.model import llm_model, sub_model
from middleware.tool_logging import ToolLoggingMiddleware
from pathlib import Path

async def get_design_subagent():
    tool_logging_middleware = ToolLoggingMiddleware(log_dir="/app/tmp/tool_log")
    prompt_content = Path("/app/sub_agents/design/agent_compact.md").read_text()

    design_subagent = SubAgent(  
        name="design_subagent",  
        description="Production-grade frontend design and UI engineering agent specialized in modern React, TailwindCSS, scalable UX systems, and real-world SaaS interfaces.",  
        system_prompt=prompt_content,   
        skills=['/app/sub_agents/design/frontend-design'],
        model=sub_model,  
        middleware=[tool_logging_middleware, summarization_middleware, make_memory_middleware("/app/sub_agents/design/memory.md")]
    )
    return design_subagent