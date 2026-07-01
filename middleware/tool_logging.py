from langchain.agents.middleware.types import AgentMiddleware  
from langchain.agents.middleware.types import AgentState, _InputAgentState, _OutputAgentState  
from typing import Any, Optional  
from langgraph.prebuilt.tool_node import ToolCallRequest
import asyncio, re
from pathlib import Path  
from datetime import datetime  

class ToolLoggingMiddleware(AgentMiddleware):  
    """툴 사용 기록(성공 및 실패 예외 포함)을 스레드별 로그 파일에 저장하는 커스텀 미들웨어."""  
      
    def __init__(self, log_dir: str = "./tool_logs"):  
        self.log_dir = Path(log_dir)  
        self.log_dir.mkdir(parents=True, exist_ok=True)  
      
    def _get_thread_id(self, runtime: Any) -> str:  
        """runtime에서 thread_id를 추출합니다."""  
        try:  
            config = getattr(runtime, "config", {})  
            thread_id = config.get("configurable", {}).get("thread_id")  
            if thread_id:  
                return str(thread_id)  
        except (AttributeError, KeyError):  
            pass  
          
        return f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  
      
    async def awrap_tool_call(  
        self,   
        request: Any,   
        handler: Any  
    ) -> Any:  
        """툴 호출을 가로채서 성공 결과 및 실패 원인을 기록합니다."""  
        tool_name = request.tool_call.get("name", "unknown")  
        tool_args = request.tool_call.get("args", {})  
        
        runtime = request.runtime  
        thread_id = self._get_thread_id(runtime) if runtime else "unknown"  
        
        log_file = self.log_dir / f"{thread_id}_tool.log"  
        timestamp = datetime.now().isoformat()  
        
        try:
            # 툴 실행 시도  
            result = await handler(request)  
            
            # 성공 시 로그 엔트리 생성
            log_entry = f"[{timestamp}] Tool: {tool_name}, Args: {tool_args}, Result: {result}\n"
            return result
            
        except Exception as e:
            # ❌ 툴 실행 실패(에러) 발생 시 가로채기
            # 에러 메시지와 함께 status='error' 포맷을 명시적으로 기록
            log_entry = (
                f"[{timestamp}] Tool: {tool_name}, Args: {tool_args}, "
                f"Result: Error invoking tool with error: {str(e)} status='error'\n"
            )
            # 에이전트 시스템 전체의 예외 처리를 방해하지 않도록 에러를 위로 다시 던짐
            raise e
            
        finally:
            # 📝 성공하든 실패하든 무조건 로그 파일에 기록 수행
            if 'log_entry' in locals():
                await asyncio.to_thread(  
                    lambda: log_file.open("a", encoding="utf-8").write(log_entry)  
                )