"""마스터 위임 가드 — 마스터가 execute(셸)로 전담 작업을 직접 처리하는 것을 차단.

마스터는 '계획·위임·통합·보고'만 담당하고 실제 작업은 서브에이전트(task 도구)에
위임해야 한다(xcu-master.md 위임 원칙). 그러나 로컬 LLM이 자주 `execute` 로 `git`/`gh`
명령을 직접 돌려 github_subagent 를 건너뛴다(로그상 gh auth/git config/gh api 등 다수).

이 미들웨어는 마스터의 `execute` 호출만 가로채, 명령의 '실제 실행 커맨드'가 git/gh 면
셸을 실행하지 않고 'github_subagent 로 위임하라'는 안내를 돌려준다. 같은 셸 명령을
반복하면 루프로 보고 중단 메시지를 준다.

주의: 이 가드는 **마스터 에이전트에만** 부착한다. coder_subagent 등은 자체 미들웨어라
영향받지 않으므로, 서브에이전트가 자기 워크스페이스에서 git 을 쓰는 것은 막지 않는다.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

SHELL_TOOL = "execute"

# 명령을 단순 커맨드 단위로 쪼개는 구분자(파이프·논리연산·서브셸·개행 등).
_SEP = re.compile(r"\|\||&&|[;&|\n()`]")
# 선행 환경변수 할당(VAR=val) 패턴.
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# 커맨드 앞에 흔히 붙는 래퍼(이걸 건너뛰고 다음 토큰을 실제 커맨드로 본다).
_WRAPPERS = {"sudo", "command", "env", "time", "nohup", "exec", "xargs"}

# git/gh 계열(로컬이든 ssh 페이로드든) → github_subagent
_GIT_CMDS = {"git", "gh", "glab"}
# 원격 접속/전송 래퍼 → 원격 작업은 coder_subagent(셸 보유)가 워크스페이스로 가져온다.
_REMOTE_CMDS = {"ssh", "sshpass", "scp", "rsync", "sftp"}
# 평문 자격증명 노출 패턴(보안 경고용).
_CRED_LEAK = re.compile(r"sshpass\s+-p|sudo\s+-S|(?:password|passwd|token|secret)\s*=", re.I)

# 반복 차단
_WINDOW = 90.0
_STOP_AT = 3
_MAX_KEYS = 1000


def _real_command_bases(command: str):
    """셸 명령 문자열에서 각 단순커맨드의 실행 파일명(basename) 집합을 추출."""
    bases = set()
    if not isinstance(command, str):
        return bases
    for seg in _SEP.split(command):
        toks = seg.strip().split()
        i = 0
        # 선행 env 할당 / 래퍼(sudo, env 등) 건너뛰기
        while i < len(toks) and (_ENV_ASSIGN.match(toks[i]) or toks[i] in _WRAPPERS):
            i += 1
        if i < len(toks):
            base = toks[i].rsplit("/", 1)[-1]   # /usr/bin/git → git
            bases.add(base)
    return bases


class MasterDelegationGuardMiddleware(AgentMiddleware):
    def __init__(self, log_dir: str = "/app/tmp/tool_log"):
        self.log_dir = Path(log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._repeat: dict = {}

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call.get("name")
        # task(서브에이전트 위임) 동일 반복 차단 — 서브가 빈 결과를 줘 마스터가 같은 task 를
        # 무한 재위임하는 루프를 끊는다(동일 subagent_type+description 가 윈도우 내 반복 시).
        if name == "task":
            try:
                a = request.tool_call.get("args") or {}
                sig = f"{a.get('subagent_type','')}|{a.get('description','')}"
                if self._is_repeat(request, sig):
                    return self._guide(
                        request,
                        f"동일한 task 를 `{a.get('subagent_type','')}` 에 반복 위임하고 있습니다. "
                        "직전 결과가 비었거나 같다면 같은 위임을 반복하지 마세요 — ① 조건·접근을 바꿔 "
                        "위임하거나 ② 지금까지 정보로 사용자에게 보고(BLOCKED)하세요.",
                        f"REPEAT/task:{a.get('subagent_type','')}")
            except Exception as e:
                logger.warning(f"MasterDelegationGuard task반복체크 건너뜀: {e}")
            return await handler(request)

        if name != SHELL_TOOL:
            return await handler(request)

        args = request.tool_call.get("args") or {}
        command = args.get("command", "")
        if not isinstance(command, str) or not command.strip():
            return await handler(request)

        bases = _real_command_bases(command)            # 각 세그먼트 첫 토큰
        is_remote = bool(bases & _REMOTE_CMDS)          # ssh/sshpass/scp/rsync/sftp
        is_git = bool(bases & _GIT_CMDS)                # 로컬 git/gh (첫 토큰, 정밀)
        # ssh 페이로드 속 원격 git 은 is_remote 로 이미 잡히므로 별도 스캔 불필요(오탐 방지).
        if not (is_remote or is_git):
            return await handler(request)               # 위임 대상 아님 → 통과

        cred_warn = ""
        if _CRED_LEAK.search(command):
            cred_warn = ("\n⚠️ 평문 비밀번호/토큰이 명령에 포함돼 로그에 남습니다. "
                         "자격증명을 명령줄에 넣지 말고, 접속·인증은 전담 서브에이전트에 맡기세요.")

        # 메시지/태그 결정
        if is_remote:
            tag = "DELEGATE/remote"
            text = ("원격 서버 작업(ssh/sshpass/scp/rsync)을 마스터가 `execute` 로 직접 하면 "
                    "안 됩니다. 마스터는 위임만 합니다. **원격 자료 수집·셸 작업은 "
                    "`coder_subagent`(task, subagent_type='coder_subagent')** 로 위임해 "
                    "필요한 폴더를 워크스페이스로 가져오게 하고, **GitHub 반영은 "
                    "`github_subagent`** 가 `git_bulk_push`(폴더 경로) 로 처리하게 하세요. "
                    "원격에서 git을 직접 세팅·푸시하지 마세요." + cred_warn)
        else:  # 로컬 git/gh
            tag = "DELEGATE/git"
            text = ("GitHub 작업을 `execute` 셸(git/gh)로 직접 처리하면 안 됩니다. 마스터는 "
                    "위임만 합니다. **`task` 도구에 `subagent_type='github_subagent'`** 로 넘겨 "
                    "github_subagent 가 GitHub MCP 도구/`git_bulk_push` 로 수행하게 하세요. "
                    "(gh/git CLI·토큰 직접 조회 금지)" + cred_warn)

        try:
            if self._is_repeat(request, command):
                text = ("같은 셸 명령을 반복 시도하고 있습니다. 직접 실행을 멈추세요. " + text)
                tag = "REPEAT/" + tag
        except Exception as e:
            logger.warning(f"MasterDelegationGuard 반복체크 건너뜀: {e}")

        return self._guide(request, text, tag)

    # ---------- 반복 차단 ----------
    def _is_repeat(self, request, command) -> bool:
        now = time.monotonic()
        if len(self._repeat) > _MAX_KEYS:
            self._repeat = {k: v for k, v in self._repeat.items() if now - v["ts0"] <= _WINDOW}
        tid = self._get_thread_id(getattr(request, "runtime", None))
        key = (tid, command.strip())
        ent = self._repeat.get(key)
        if ent is None or now - ent["ts0"] > _WINDOW:
            self._repeat[key] = {"ts0": now, "count": 1}
            return False
        ent["count"] += 1
        return ent["count"] >= _STOP_AT

    # ---------- 안내 + 로깅 ----------
    def _guide(self, request, text, tag):
        tcid = request.tool_call.get("id", "")
        try:
            asyncio.create_task(self._log(request, tag, text))
        except RuntimeError:
            pass
        return ToolMessage(content=f"[위임가드] {text}", tool_call_id=tcid,
                           name=request.tool_call.get("name", SHELL_TOOL))

    async def _log(self, request, tag, detail):
        try:
            tid = self._get_thread_id(getattr(request, "runtime", None))
            cmd = (request.tool_call.get("args") or {}).get("command", "")
            ts = datetime.now().isoformat()
            entry = (f"[{ts}] [thread={tid}] MASTER_DELEGATION_GUARD [{tag}]\n"
                     f"  CMD: {cmd}\n  -> {detail}\n")
            for fn in (f"{tid}_tool.log", "master_delegation_guard.log"):
                await asyncio.to_thread(
                    lambda p=self.log_dir / fn: p.open("a", encoding="utf-8").write(entry))
        except Exception as e:
            logger.warning(f"MasterDelegationGuard 로그 실패: {e}")

    def _get_thread_id(self, runtime) -> str:
        try:
            config = getattr(runtime, "config", {})
            tid = config.get("configurable", {}).get("thread_id")
            if tid:
                return str(tid)
        except Exception:
            pass
        return f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
