"""XCU Chainlit 앱.

- 로그인: SQLite app_users 테이블 + bcrypt (password_auth_callback)
- 챗봇: 기존 deepagents 마스터 에이전트 재사용, 토큰/툴 스트리밍
- 영속화: 챗 히스토리는 SQLite Data Layer, 에이전트 상태는 SQLite 체크포인터
"""
import os
import chainlit as cl
from chainlit.input_widget import Switch
from langchain_core.messages import HumanMessage, SystemMessage

from database import CHAINLIT_DB_PATH, init_db, verify_user
from data_layer import SQLiteDataLayer
from agent_runtime import get_master_agent
from llm_conn.model import llm_model
from guardrails import check_injection, log_block, REFUSAL
from langgraph.errors import GraphRecursionError

# 앱 임포트 시점에 테이블 보장
init_db()

# 관리자 콘솔(/admin) 라우트 등록 (chainlit.server.app 에 부착)
import admin  # noqa: E402,F401

_CONNINFO = f"sqlite+aiosqlite:///{CHAINLIT_DB_PATH}"


@cl.data_layer
def get_data_layer():
    """챗 히스토리 영속화(SQLite)."""
    return SQLiteDataLayer(conninfo=_CONNINFO)


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """SQLite 자격증명 검증."""
    user = verify_user(username, password)
    if not user:
        return None
    return cl.User(
        identifier=user["identifier"],
        metadata={"display_name": user["display_name"], "role": user["role"]},
    )



# 채팅 입력창 옆 설정(⚙️)에서 '이번 대화에 사용할 데이터 소스'를 체크(복수)한다.
# 데이터 소스 3종(웹검색·DB조회·사내문서)만 게이팅 대상:
#   체크된 것 → 반드시 사용, 체크 안 된 데이터 소스 → 사용 금지.
# time·document·coder 등 나머지 에이전트는 마스터가 자유롭게 사용(게이팅 안 함).
# (서브에이전트명, 표시 라벨)
_AGENT_OPTIONS = [
    ("search_subagent", "웹 검색"),
    ("elasticsearch_subagent", "DB·로그 조회"),
    ("chroma_subagent", "사내문서 검색"),
]
# 게이팅 대상(데이터 소스) — 순서 보존 리스트 + 집합
_DATA_SOURCES_ORDER = [aid for aid, _ in _AGENT_OPTIONS]
_DATA_SOURCES = set(_DATA_SOURCES_ORDER)


async def _send_agent_settings():
    """입력창 설정 패널에 에이전트별 on/off 스위치(체크)를 띄운다.

    이미 선택된(체크된) 에이전트는 다시 열어도 체크 상태로 표기한다.
    """
    enabled = set(cl.user_session.get("forced_agents") or [])
    await cl.ChatSettings(
        [Switch(id=aid, label=label, initial=(aid in enabled))
         for aid, label in _AGENT_OPTIONS]
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict):
    # 켜진 에이전트만 모아 세션에 저장 → on_message에서 강제 위임에 사용.
    enabled = [aid for aid, _ in _AGENT_OPTIONS if settings.get(aid)]
    cl.user_session.set("forced_agents", enabled)
    # 프런트(⚙️ 옆 칩) 표시용: 사용자별 선택 라벨을 백엔드에 저장 → custom.js가 폴링.
    labels = [lbl for aid, lbl in _AGENT_OPTIONS if aid in set(enabled)]
    admin.SELECTED_AGENTS[_user_id()] = labels


@cl.on_chat_start
async def on_chat_start():
    # 에이전트 사전 워밍업(서브에이전트/ MCP 세션 초기화)
    await get_master_agent()
    admin.SELECTED_AGENTS[_user_id()] = []   # 새 세션은 선택 없음(칩 비움)
    await _send_agent_settings()  # 입력창 설정에 에이전트 체크 스위치 노출


@cl.on_chat_resume
async def on_chat_resume(thread):
    # 체크포인터(thread_id 기준)가 에이전트 상태를 복원하므로 별도 작업 불필요.
    admin.SELECTED_AGENTS[_user_id()] = []   # 재개 시 선택 초기화(스위치도 off로 표시)
    await _send_agent_settings()
    await get_master_agent()


def _thread_id() -> str:
    return cl.context.session.thread_id


def _user_id() -> str:
    user = cl.user_session.get("user")
    return user.identifier if user else "anonymous"


# --- 산출물 자동 첨부 (다운로드) ---
ARTIFACT_ROOT = "/app/tmp/workspace"
_ARTIFACT_EXCLUDE_DIRS = {"large_tool_results"}
_MAX_ATTACH = 10
_MAX_ATTACH_BYTES = 50 * 1024 * 1024  # 50MB


def _scan_artifacts() -> dict:
    snap = {}
    for dirpath, dirnames, filenames in os.walk(ARTIFACT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _ARTIFACT_EXCLUDE_DIRS]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                snap[fp] = os.path.getmtime(fp)
            except OSError:
                pass
    return snap


async def _attach_new_artifacts(answer, before: dict) -> None:
    """이번 턴에 새로 생성/수정된 산출물 파일을 답변에 다운로드 가능하게 첨부."""
    try:
        after = _scan_artifacts()
        new = [fp for fp, m in after.items() if fp not in before or m > before.get(fp, 0)]
        count = 0
        for fp in sorted(new):
            try:
                if os.path.getsize(fp) > _MAX_ATTACH_BYTES:
                    continue
            except OSError:
                continue
            el = cl.File(name=os.path.basename(fp), path=fp, display="inline")
            await el.send(for_id=answer.id, persist=False)  # blob 미설정 -> 영속화 생략(라이브 다운로드만)
            count += 1
            if count >= _MAX_ATTACH:
                break
    except Exception:
        pass


async def _clear_steps(steps) -> None:
    """결과 확정 후 도구 사용 흔적(스텝)을 UI/히스토리에서 제거."""
    for st in steps:
        try:
            await st.remove()
        except Exception:
            pass


async def _summarize_partial(agent, config):
    """한도 도달 등 중단 시, 체크포인트의 중간 진행 내용으로 최종 정리 답변을 생성한다."""
    try:
        state = await agent.aget_state(config)
        vals = getattr(state, "values", None) or {}
        msgs = vals.get("messages", []) if isinstance(vals, dict) else []
        chunks = []
        for m in msgs[-40:]:
            c = getattr(m, "content", "")
            if isinstance(c, str) and c.strip():
                chunks.append(c.strip())
        ctx = "\n\n".join(chunks)[-8000:]
        if not ctx:
            return None
        resp = await llm_model.ainvoke([
            SystemMessage(content=(
                "아래는 한 작업의 중간 진행/수집 내용이다. 이를 바탕으로 사용자에게 줄 최종 "
                "정리 답변을 한국어로 간결하게 작성하라. 미완료라면 지금까지 확인된 내용과 "
                "남은 부분을 명확히 구분해 알려라.")),
            HumanMessage(content=ctx),
        ])
        out = getattr(resp, "content", None)
        return out if isinstance(out, str) and out.strip() else None
    except Exception:
        return None


@cl.on_message
async def on_message(message: cl.Message):
    # 입력 가드레일: 프롬프트 인젝션/추출/정체성 변경 시도 차단
    _inj = check_injection(message.content)
    if _inj:
        log_block(_user_id(), _inj, message.content)
        await cl.Message(content=REFUSAL, author="엑큐").send()
        return

    agent = await get_master_agent()

    config = {
        "configurable": {
            "thread_id": _thread_id(),
            "user_id": _user_id(),
        },
        "recursion_limit": 300,
    }

    # 데이터 소스 게이팅: 체크된 데이터 소스만 사용, 체크 안 된 데이터 소스는 금지.
    # 그 외 에이전트(time·document·coder 등)는 자유. 사용자 메시지 앞에 지시를 붙인다
    # (로컬 모델은 별도 시스템 메시지보다 사용자 메시지를 더 강하게 따름).
    _checked = [a for a in (cl.user_session.get("forced_agents") or [])
                if a in _DATA_SOURCES]
    _user_text = message.content
    if _checked:  # 하나도 체크 안 했으면 자동(제약 없음)
        _allow = ", ".join(f"`{a}`" for a in _checked)
        _forbid = ", ".join(f"`{a}`" for a in _DATA_SOURCES_ORDER if a not in _checked)
        _user_text = (
            f"[필수 지시 — 반드시 준수] 이 요청의 **데이터 수집은 오직 {_allow}만** 사용한다. "
            f"나머지 데이터 소스({_forbid})는 보조·교차확인 목적이라도 **절대 사용 금지**다. "
            f"단, 데이터 소스가 아닌 다른 에이전트(`document_subagent`·`coder_subagent` 등)는 "
            f"작업에 필요하면 자유롭게 사용하라 — 특히 **날짜·기간이 관련되면(오늘·어제·최근 N일 등이거나 "
            f"현재 날짜 기준이 필요하면) 반드시 먼저 `get_current_time` 툴로 절대 날짜를 확정한 뒤** 조회하라 "
            f"(날짜를 모른 채 추측하거나 날짜 조건을 생략하지 마라).\n\n"
            f"{message.content}"
        )
    _input_messages = [HumanMessage(content=_user_text)]

    # 이번 턴에 새로 생성될 산출물 감지용 스냅샷
    _artifacts_before = _scan_artifacts()

    # 답변 메시지: 반드시 "최상위 메시지"로 만들어 스레드에 정상 저장/표시되게 한다.
    # (parent_id가 비정상으로 잡히면 프론트엔드가 부모를 못 찾아 답변이 화면/히스토리에서 사라진다)
    answer = cl.Message(content="", author="엑큐")
    answer.parent_id = None
    await answer.send()  # 빈 본문으로 먼저 생성/영속화

    tool_steps: dict = {}
    all_steps: list = []  # 완료 후 제거할 도구 스텝 모음
    _dbg = {"master": 0, "sub": 0, "tools": 0}  # 동시성 진단 카운터

    try:
        async for event in agent.astream_events(
            {"messages": _input_messages},
            config=config,
            version="v2",
            subgraphs=False,
            stream_mode=["messages"],
        ):
            kind = event["event"]
            metadata = event.get("metadata", {})

            # 메인 에이전트 토큰만 본문에 스트리밍 (서브에이전트 토큰 제외)
            if kind == "on_chat_model_stream" and metadata.get("lc_agent_name") is None:
                chunk = event["data"].get("chunk")
                if chunk is not None and chunk.content:
                    _dbg["master"] += 1
                    await answer.stream_token(chunk.content)
            elif kind == "on_chat_model_stream":
                _dbg["sub"] += 1  # 서브에이전트 토큰(본문 미스트리밍)

            # 툴 실행 시작 -> 스텝 생성 (답변 밑으로 중첩되지 않도록 최상위로)
            elif kind == "on_tool_start":
                _dbg["tools"] += 1
                step = cl.Step(name=event["name"], type="tool")
                step.parent_id = None
                step.input = str(event["data"].get("input", ""))[:500]
                await step.send()
                tool_steps[event["run_id"]] = step
                all_steps.append(step)

            # 툴 실행 종료 -> 스텝 출력 갱신
            elif kind == "on_tool_end":
                step = tool_steps.pop(event["run_id"], None)
                if step is not None:
                    step.output = str(event["data"].get("output", ""))[:800]
                    await step.update()

            # 체인 에러
            elif kind == "on_chain_error":
                err = str(event["data"].get("error", ""))
                if answer.content:
                    answer.content += f"\n\n⚠️ 오류: {err}"
                else:
                    answer.content = f"⚠️ 오류가 발생했습니다: {err}"

    except Exception as e:
        is_limit = isinstance(e, GraphRecursionError) or "recursion" in str(e).lower()
        if answer.content:
            answer.content += (
                "\n\n— ⚠️ 작업이 한도에 도달해 중단되었습니다(위는 부분 결과)."
                if is_limit else f"\n\n— ⚠️ 오류로 중단되었습니다: {e}"
            )
        else:
            summary = await _summarize_partial(agent, config) if is_limit else None
            if summary:
                answer.content = summary + "\n\n— ⚠️ 작업 한도 도달로 중간까지의 내용을 정리한 답변입니다."
            elif is_limit:
                answer.content = "⚠️ 작업이 너무 길어져 한도에 도달해 중단됐습니다. 요청을 더 좁혀 다시 시도해 주세요."
            else:
                answer.content = f"⚠️ 작업이 중단되었습니다: {e}"
        answer.parent_id = None
        await answer.update()
        await _clear_steps(all_steps)
        return

    # 동시성 진단: 마스터 토큰이 0이면(=빈 응답) 상태를 로그로 남긴다.
    print(f"[xcu] turn done thread={_thread_id()} user={_user_id()} "
          f"master_tok={_dbg['master']} sub_tok={_dbg['sub']} tools={_dbg['tools']} "
          f"content_len={len(answer.content)}", flush=True)
    if not answer.content:
        answer.content = "(응답이 비어 있습니다)"
    # 이번 턴에 생성된 산출물 파일을 다운로드 첨부
    await _attach_new_artifacts(answer, _artifacts_before)
    # 최종 저장 직전 최상위 보장
    answer.parent_id = None
    await answer.update()
    # 결과가 다 나왔으면 도구 사용 흔적(스텝) 제거
    await _clear_steps(all_steps)
