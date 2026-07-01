"""git_bulk_push — 로컬 폴더를 한 번에 커밋·푸시하는 결정론적 도구.

MCP `push_files`/`create_or_update_file` 는 파일 '내용'을 인자로 인라인해야 해서
파일이 많으면 작은 로컬 모델이 거대한 호출을 못 만들고, 하나씩 하면 호출 횟수가
폭발한다. 이 도구는 **모델이 디렉터리 경로만** 주면 git CLI 로 폴더 전체를 한 커밋에
올린다(내용 읽기·인라인 불필요).

핵심 안전장치:
- `.env`·키·자격증명 등 시크릿은 .gitignore 처리 + 추적 해제 후, 스테이징된 파일을
  최종 스캔해 시크릿이 하나라도 잡히면 **푸시를 중단**한다(절대 노출 금지).
- 토큰은 origin 에 저장하지 않고 push URL 로만 일시 사용하며, 모든 반환/로그에서 마스킹.

순수 로직은 bulk_push()에 있고 @tool 래퍼(git_bulk_push)가 이를 감싼다.
"""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# 클론에 덮어쓸 때 건너뛸 디렉터리(.git 은 클론 쪽을 보존해야 하므로 필수 제외).
# large_tool_results: 하니스가 거대 도구결과를 떨구는 스크래치 폴더 — 절대 푸시 금지.
_SKIP_COPY_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
                   "env", ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache",
                   "large_tool_results", "tool_log", ".cache"}

# ── 정리(cleanup) 안전 범위: 이 루트 '하위'만 삭제 허용(루트 자체·외부 경로는 거부) ──
ALLOWED_CLEANUP_ROOTS = [
    Path(p).resolve()
    for p in os.environ.get("GBP_CLEANUP_ROOTS", "/app/tmp/workspace").split(":")
    if p.strip()
]

# ── 시크릿: 추적 해제 + 최종 스캔에서 걸리면 푸시 중단 ──────────────────────────
SECRET_GLOBS = [
    ".env", ".env.*", "*.env",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks",
    "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*", "id_dsa*", "id_ecdsa*",
    ".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json",
    "*.secret", "secrets.yml", "secrets.yaml", "*service-account*.json",
]
# ── 빌드/캐시: 새로 스테이징되지 않도록 .gitignore 에만 추가(기존 추적은 건드리지 않음) ──
IGNORE_LINES = [
    "__pycache__/", "*.pyc", "*.pyo", ".venv/", "venv/", "env/",
    "node_modules/", "*.egg-info/", ".DS_Store", ".ipynb_checkpoints/",
    "large_tool_results/", "tool_log/", ".cache/",
]
_IGNORE_MARK = "# >>> git_bulk_push managed (build/cache) >>>"
_IGNORE_END = "# <<< git_bulk_push managed <<<"

GITHUB_MCP_JSON = "/app/sub_agents/github/mcp.json"


def _is_secret(path: str) -> bool:
    name = os.path.basename(path)
    for pat in SECRET_GLOBS:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, "*/" + pat):
            return True
    return False


def _get_token() -> str | None:
    for var in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(var)
        if v:
            return v.strip()
    # mcp.json 의 Authorization: Bearer <token> 재사용
    try:
        cfg = json.loads(Path(GITHUB_MCP_JSON).read_text())
        auth = cfg["mcpServers"]["github"]["headers"]["Authorization"]
        return auth.split(None, 1)[1].strip()  # "Bearer xxx" -> "xxx"
    except Exception:
        return None


def _remote_url(owner: str, repo: str, token: str) -> str:
    # 별도 함수로 둬 테스트에서 로컬 bare repo 로 교체(monkeypatch) 가능.
    return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"


def _scrub(text: str, token: str | None) -> str:
    if not text:
        return text
    if token:
        text = text.replace(token, "***")
    # 혹시 모를 토큰형 문자열도 마스킹
    return re.sub(r"ghp_[A-Za-z0-9]+", "ghp_***", text)


def _run(args, cwd, token=None, timeout=180):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    out = _scrub((p.stdout or "") + (p.stderr or ""), token)
    return p.returncode, out.strip()


def _ensure_gitignore(repo_dir: Path):
    gi = repo_dir / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    if _IGNORE_MARK in existing:
        return
    # 시크릿 + 빌드/캐시 모두 ignore 에 추가해 애초에 스테이징되지 않게 한다.
    block = "\n".join([_IGNORE_MARK, *SECRET_GLOBS, *IGNORE_LINES, _IGNORE_END]) + "\n"
    sep = "" if existing.endswith("\n") or not existing else "\n"
    gi.write_text(existing + sep + block)


def _within_allowed(target: Path):
    """target 이 허용 루트의 '하위'면 (True, root). 루트 자체/외부면 (False, None).

    경로 중간의 심링크는 resolve 로 평가(탈출 방지)하되, **마지막 구성요소는
    따라가지 않는다** — 워크스페이스 안에 있는 심링크 자체는 (대상이 밖이어도)
    링크만 제거할 수 있게 하기 위함. 실제 삭제 시 is_symlink 를 먼저 보고 unlink 한다.
    """
    try:
        t = target.expanduser()
        t = t.parent.resolve() / t.name   # 부모까지만 resolve, 최종 요소는 보존
    except Exception:
        return False, None
    for root in ALLOWED_CLEANUP_ROOTS:
        try:
            t.relative_to(root)
        except ValueError:
            continue
        if t != root and len(t.parts) > len(root.parts):
            return True, root
    return False, None


def safe_cleanup(path: str) -> dict:
    """외부에서 가져온 임시 폴더/파일을 안전 범위(워크스페이스 하위) 안에서만 삭제."""
    p = Path(path).expanduser()
    if not p.exists() and not p.is_symlink():
        return {"ok": True, "note": f"이미 없음: {path}"}
    ok, root = _within_allowed(p)
    if not ok:
        return {"ok": False,
                "error": (f"안전 범위 밖이라 삭제를 거부했습니다: {path}. "
                          f"허용 루트({', '.join(map(str, ALLOWED_CLEANUP_ROOTS))}) 하위만 삭제 가능합니다.")}
    try:
        if p.is_symlink():
            p.unlink()  # 심링크는 대상 따라가지 않고 링크만 제거
        elif p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"ok": True, "note": f"삭제 완료: {path}"}
    except Exception as e:
        return {"ok": False, "error": f"삭제 실패: {e}"}


def _copy_overlay(src: Path, dst: Path):
    """src 의 작업 파일을 dst(클론된 저장소) 위에 덮어쓴다(.git·빌드/캐시 제외)."""
    for root, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x not in _SKIP_COPY_DIRS]
        rel = os.path.relpath(root, src)
        target = dst if rel == "." else dst / rel
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            try:
                shutil.copy2(os.path.join(root, f), target / f)
            except Exception:
                pass


def bulk_push(local_dir: str, repo: str, message: str,
              owner: str = "XCURENETGIT", branch: str = "main",
              cleanup_after_push: bool = False) -> dict:
    """폴더 내용을 원격 저장소에 동기화한다(clone→overlay→commit→push).

    원격을 clone 해 그 히스토리 위에 로컬 파일을 덮어쓰고 커밋하므로, 원격에 기존
    커밋이 있어도 **fast-forward 로 안전하게** push 된다(force push 불필요, 히스토리 보존).
    """
    d = Path(local_dir).expanduser()
    if not d.is_dir():
        return {"ok": False, "error": f"디렉터리가 없습니다: {local_dir}"}
    if not repo:
        return {"ok": False, "error": "repo 가 필요합니다."}
    token = _get_token()
    if not token:
        return {"ok": False, "error": "GitHub 토큰을 찾지 못했습니다(env 또는 mcp.json)."}

    ident = ["-c", "user.name=xcu-bot", "-c", "user.email=bot@xcurenet.local"]
    url = _remote_url(owner, repo, token)
    work = Path(tempfile.mkdtemp(prefix="gbp_"))
    repo_dir = work / "repo"
    try:
        # 1) 원격 clone (히스토리 확보). 빈 저장소도 clone 은 성공한다.
        rc, out = _run(["git", "clone", url, str(repo_dir)], work, token, timeout=300)
        if rc != 0:
            return {"ok": False, "error": f"clone 실패: {out}",
                    "hint": "저장소가 없으면 먼저 create_repository 로 생성하세요(owner/repo 확인)."}

        # 2) 대상 브랜치 준비: 원격에 있으면 체크아웃, 없으면 새로 만든다.
        rc, _ = _run(["git", "checkout", branch], repo_dir, token)
        if rc != 0:
            rc, out = _run(["git", "checkout", "-B", branch], repo_dir, token)
            if rc != 0:
                return {"ok": False, "error": f"브랜치 준비 실패({branch}): {out}"}

        # 3) 로컬 파일을 클론 위에 덮어쓰기(overlay)
        _copy_overlay(d, repo_dir)

        # 4) 빌드/캐시 .gitignore + 시크릿 추적 해제
        _ensure_gitignore(repo_dir)
        for pat in SECRET_GLOBS:
            _run(["git", "rm", "-r", "--cached", "--ignore-unmatch", pat], repo_dir, token)
            _run(["git", "rm", "-r", "--cached", "--ignore-unmatch", f"*/{pat}"], repo_dir, token)

        # 5) 스테이징
        rc, out = _run(["git", "add", "-A"], repo_dir, token)
        if rc != 0:
            return {"ok": False, "error": f"git add 실패: {out}"}

        # 6) 시크릿 처리: 스테이징된 시크릿은 자동 unstage(나머지는 정상 푸시).
        rc, staged = _run(["git", "diff", "--cached", "--name-only"], repo_dir, token)
        staged_files = [s for s in staged.splitlines() if s.strip()]
        leaked = [s for s in staged_files if _is_secret(s)]
        excluded_secrets = []
        if leaked:
            for s in leaked:
                _run(["git", "reset", "-q", "--", s], repo_dir, token)
            excluded_secrets = leaked[:20]
            rc, staged = _run(["git", "diff", "--cached", "--name-only"], repo_dir, token)
            staged_files = [s for s in staged.splitlines() if s.strip()]
            still = [s for s in staged_files if _is_secret(s)]
            if still:
                return {"ok": False, "error": "시크릿을 제외하지 못해 푸시를 중단했습니다.",
                        "secrets": still[:20]}

        # 7) 커밋(변경 없으면 스킵)
        committed = bool(staged_files)
        if committed:
            rc, out = _run(["git", *ident, "commit", "-m", message], repo_dir, token)
            if rc != 0:
                if "nothing to commit" in out:
                    committed = False
                else:
                    return {"ok": False, "error": f"커밋 실패: {out}"}

        if not committed:
            # 변경 없음 = 원격과 이미 동일(데이터는 원격에 있음) → 성공 처리. cleanup 도 적용.
            result = {"ok": True, "owner": owner, "repo": repo, "branch": branch,
                      "files": 0, "committed": False, "commit": "",
                      "url": f"https://github.com/{owner}/{repo}/tree/{branch}",
                      "excluded_secrets": excluded_secrets,
                      "note": "변경 없음(원격과 동일) — 푸시할 내용 없음"}
        else:
            # 8) push (clone 기준이라 fast-forward). 토큰은 URL 로만 일시 사용.
            rc, out = _run(["git", *ident, "push", url, f"HEAD:refs/heads/{branch}"],
                           repo_dir, token, timeout=300)
            if rc != 0:
                return {"ok": False, "error": f"push 실패: {out}",
                        "hint": "보호 브랜치면 다른 branch 로 올린 뒤 create_pull_request 하세요."}
            rc, sha = _run(["git", "rev-parse", "HEAD"], repo_dir)
            result = {
                "ok": True,
                "owner": owner, "repo": repo, "branch": branch,
                "files": len(staged_files),
                "committed": True,
                "commit": sha[:40],
                "url": f"https://github.com/{owner}/{repo}/tree/{branch}",
                "excluded_secrets": excluded_secrets,
                "note": f"{len(staged_files)}개 파일 변경을 1개 커밋으로 푸시",
            }
    finally:
        shutil.rmtree(work, ignore_errors=True)   # 임시 클론은 항상 제거

    # push 성공 후에만 정리(외부에서 가져온 임시 폴더일 때). 실패 시엔 절대 삭제하지 않는다.
    if cleanup_after_push:
        result["cleanup"] = safe_cleanup(local_dir)
    return result


# ── LangChain @tool 래퍼 (컨테이너에서만 import 가능) ────────────────────────────
def make_git_bulk_push_tool():
    from langchain_core.tools import tool

    @tool
    def git_bulk_push(local_dir: str, repo: str, message: str,
                      owner: str = "XCURENETGIT", branch: str = "main",
                      cleanup_after_push: bool = False) -> str:
        """로컬 디렉터리 전체를 한 번에 커밋·푸시한다. 파일 내용을 읽거나 인라인할 필요 없이
        **디렉터리 경로만** 주면 된다. 파일이 여러 개이거나 폴더를 통째로 올릴 때 이 도구를 쓴다.
        (단일/소수 파일 편집은 create_or_update_file 을 쓴다.)

        Args:
            local_dir: 푸시할 로컬 폴더 경로 (예: /app/tmp/workspace/emass_ai_module).
            repo: 대상 저장소명 (조직/계정명이 아니라 실제 repo 이름).
            message: 커밋 메시지.
            owner: 저장소 owner. 조직이면 XCURENETGIT(기본), 개인이면 get_me 의 login.
            branch: 푸시할 브랜치(기본 main). 보호 브랜치면 다른 브랜치로 올리고 PR 을 만든다.
            cleanup_after_push: True 면 push 성공 후 local_dir 을 삭제한다. **원격서버 등
                외부에서 가져온 임시 폴더를 push 한 경우, 사용자가 보존을 지시하지 않았다면
                True 로 호출**해 작업 후 정리한다. (워크스페이스 하위만 삭제되며 push 실패 시엔 삭제 안 함)

        .env·키·자격증명 등 시크릿은 자동 제외되며, 발견 시 푸시가 중단된다.
        """
        r = bulk_push(local_dir, repo, message, owner=owner, branch=branch,
                      cleanup_after_push=cleanup_after_push)
        if r.get("ok"):
            s = (f"[SUCCESS] {r['note']}\n"
                 f"owner/repo: {r['owner']}/{r['repo']} (branch {r['branch']})\n"
                 f"commit: {r['commit']}\nurl: {r['url']}")
            if r.get("excluded_secrets"):
                s += "\n자동 제외된 시크릿: " + ", ".join(r["excluded_secrets"])
            if r.get("cleanup"):
                c = r["cleanup"]
                s += "\n정리: " + (c.get("note") if c.get("ok") else f"실패 - {c.get('error')}")
            return s
        msg = f"[FAIL] {r.get('error')}"
        if r.get("secrets"):
            msg += "\n제외 필요 시크릿: " + ", ".join(r["secrets"])
        if r.get("hint"):
            msg += "\nhint: " + r["hint"]
        return msg

    return git_bulk_push


def make_cleanup_tool():
    from langchain_core.tools import tool

    @tool
    def cleanup_fetched_path(path: str) -> str:
        """원격서버 등 외부에서 가져온 임시 폴더/파일을 삭제한다. push 없이 가져오기만 한
        자료를 작업 후 정리할 때 쓴다. 사용자가 보존을 지시하지 않은 외부 임시 자료에만 사용.

        안전: 워크스페이스 하위 경로만 삭제 가능하며, 루트 자체·외부 경로·사용자의 영구
        프로젝트 폴더는 거부된다. 되돌릴 수 없으니 임시 가져온 자료에만 사용한다.
        """
        r = safe_cleanup(path)
        return ("[SUCCESS] " + r["note"]) if r.get("ok") else ("[FAIL] " + r["error"])

    return cleanup_fetched_path
