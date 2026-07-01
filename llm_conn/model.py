from langchain.chat_models import init_chat_model 
import json  
import requests  
import time 

llm_model = init_chat_model(
    "xcn_llm",
    model_provider="openai",
    base_url="http://vllm-server:8000/v1",
    api_key="xq_agent",
    temperature=0.5,          # ← 0.1에서 상향 (Qwen3 권장)
    top_p=0.95,
    presence_penalty=0.8,     # 반복 억제
    max_tokens=8192,
    #profile={"max_input_tokens": 256000},
    stream_chunk_timeout=None,
    model_kwargs={"extra_body": {"top_k": 20, "min_p": 0}},  # top_k/min_p는 vLLM 확장
)

sub_model = init_chat_model(
    "xcn_llm",
    model_provider="openai",
    base_url="http://vllm-server:8000/v1",
    api_key="xq_agent",
    temperature=0.3,          # 0.1 → 0.4: greedy 탈피로 반복퇴화(동일 tool call 루프) 완화. 0.7+는 tool-call 인자 정밀도 저하 우려라 중간값.
    top_p=0.95,
    presence_penalty=0.8,     # 0.0 → 0.5: 동일 토큰열(=같은 쿼리) 재생산 억제. 마스터(1.0)보다 낮게 둬 구조적 tool-call JSON은 보호.
    frequency_penalty=0.5,    # 반복 횟수에 비례한 추가 억제(같은 쿼리 N회 반복 시 점점 더 불리)
    max_tokens=8192,
    #profile={"max_input_tokens": 256000},
    stream_chunk_timeout=None,
    # thinking 비활성화: 라우팅·기계적 툴호출에 불필요한 <think> 생성 제거(지연 단축)
    model_kwargs={"extra_body": {"top_k": 20, "min_p": 0, "chat_template_kwargs": {"enable_thinking": False}}},
    #model_kwargs={"extra_body": {"top_k": 20, "min_p": 0}},
)