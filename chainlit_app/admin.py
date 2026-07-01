"""관리자 콘솔 + 공용 보조 API.

Chainlit이 사용하는 동일한 FastAPI 서버(chainlit.server.app)에 라우트를 얹는다.
- /admin            : 관리자 콘솔(HTTP Basic + role=admin)
  - 사용자 추가/삭제, 모든 세션 열람
  - 벡터 DB 문서 추가 (ChromaDB 연동 예정 — 현재는 UI 스캐폴드)
- /api/whoami       : 로그인 사용자 정보(사이드바 환영 배너용, Chainlit 인증 쿠키 기반)
"""
from fastapi import Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse

from fastapi.security import HTTPBasic, HTTPBasicCredentials

from chainlit.server import app
from chainlit.auth import get_current_user

import database as db
import vectordb

_basic = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    """Basic 인증 자격증명을 검증하고 admin 권한을 요구한다."""
    user = db.verify_user(credentials.username, credentials.password)
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자 권한이 필요합니다.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ----------------------------- 공용: 현재 사용자 -----------------------------

@app.get("/api/whoami")
async def whoami(current_user=Depends(get_current_user)):
    """로그인한 사용자 정보(사이드바 환영 배너용)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    md = getattr(current_user, "metadata", None) or {}
    return {
        "identifier": current_user.identifier,
        "display_name": md.get("display_name", current_user.identifier),
    }


# 사용자별 선택 에이전트(라벨 리스트). app.py on_settings_update 가 갱신,
# 프런트 custom.js 가 폴링해 설정(⚙️) 아이콘 옆에 표시한다.
SELECTED_AGENTS: dict[str, list] = {}


@app.get("/api/selected_agents")
async def selected_agents(current_user=Depends(get_current_user)):
    """현재 사용자가 선택(체크)한 에이전트 라벨 목록."""
    ident = current_user.identifier if current_user else None
    return {"agents": SELECTED_AGENTS.get(ident, [])}


# ----------------------------- 사용자 관리 -----------------------------

@app.get("/admin/api/users")
def admin_list_users(_: str = Depends(require_admin)):
    return {"users": db.list_users()}


@app.post("/admin/api/users")
async def admin_create_user(payload: dict, _: str = Depends(require_admin)):
    identifier = (payload.get("identifier") or "").strip()
    password = payload.get("password") or ""
    display_name = (payload.get("display_name") or "").strip() or identifier
    role = payload.get("role") or "user"
    if not identifier or not password:
        raise HTTPException(400, "identifier와 password는 필수입니다.")
    if role not in ("user", "admin"):
        raise HTTPException(400, "role은 user 또는 admin이어야 합니다.")
    db.create_user(identifier, password, display_name, role)
    return {"ok": True, "identifier": identifier}


@app.delete("/admin/api/users/{identifier}")
def admin_delete_user(identifier: str, admin: str = Depends(require_admin)):
    if identifier == admin:
        raise HTTPException(400, "현재 로그인한 본인 계정은 삭제할 수 없습니다.")
    users = {u["identifier"]: u for u in db.list_users()}
    if identifier not in users:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if users[identifier]["role"] == "admin" and db.count_admins() <= 1:
        raise HTTPException(400, "마지막 관리자 계정은 삭제할 수 없습니다.")
    ok = db.delete_user(identifier)
    return {"ok": ok}


# ----------------------------- 세션 열람 -----------------------------

@app.get("/admin/api/threads")
def admin_list_threads(_: str = Depends(require_admin)):
    return {"threads": db.list_all_threads()}


@app.get("/admin/api/threads/{thread_id}")
def admin_thread_messages(thread_id: str, _: str = Depends(require_admin)):
    return {"messages": db.get_thread_messages(thread_id)}


# ----------------------------- 벡터 DB (ChromaDB + Infinity bge-m3) -----------------------------

def _decode_text(raw: bytes) -> str:
    """텍스트 바이트를 인코딩 자동 감지로 디코드(UTF-8/CP949/EUC-KR 등 한글 대응)."""
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:
        pass
    for enc in ("utf-8", "cp949", "euc-kr", "utf-16"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _ooxml_texts(data: bytes, tag: str, block: str) -> str:
    """OOXML XML에서 네임스페이스 무시하고 block 단위로 tag 텍스트를 모은다."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(data)
    local = lambda t: t.rsplit("}", 1)[-1]
    lines = []
    for el in root.iter():
        if local(el.tag) != block:
            continue
        parts = [e.text for e in el.iter() if local(e.tag) == tag and e.text]
        if parts:
            lines.append("".join(parts))
    return "\n".join(lines)


def _extract_text(filename: str, raw: bytes) -> str:
    """업로드 파일에서 텍스트 추출.

    - pdf: pypdf
    - docx/pptx/xlsx: 표준 zipfile+XML 파싱(추가 의존성 없음)
    - txt/md/csv/log/json 등: 인코딩 자동 감지 디코드(한글 CP949/EUC-KR 포함)
    - 인식 불가한 바이너리(ZIP 등): 깨진 텍스트 적재 대신 명확히 거절
    """
    import io
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            raise HTTPException(400, f"PDF 텍스트 추출 실패: {e}")
    if name.endswith((".docx", ".pptx", ".xlsx")):
        import re as _re
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if name.endswith(".docx"):
                    return _ooxml_texts(z.read("word/document.xml"), "t", "p")
                if name.endswith(".pptx"):
                    slides = sorted(n for n in z.namelist()
                                    if _re.match(r"ppt/slides/slide\d+\.xml$", n))
                    return "\n".join(_ooxml_texts(z.read(n), "t", "p") for n in slides)
                # .xlsx: 공유 문자열 테이블의 셀 텍스트
                try:
                    ss = z.read("xl/sharedStrings.xml")
                except KeyError:
                    return ""
                return _ooxml_texts(ss, "t", "si")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"문서 텍스트 추출 실패: {e}")
    if raw[:4] == b"PK\x03\x04":      # OOXML/ZIP인데 위 확장자가 아님
        raise HTTPException(400, "지원하지 않는 형식입니다. txt·md·csv·log·json·pdf·docx·pptx·xlsx 파일을 올려주세요.")
    return _decode_text(raw)


@app.get("/admin/api/vectordb/collections")
def vectordb_collections(_: str = Depends(require_admin)):
    try:
        return {"collections": vectordb.list_collections()}
    except Exception as e:
        raise HTTPException(503, f"ChromaDB 연결 실패: {e}")


@app.get("/admin/api/vectordb/health")
def vectordb_health(_: str = Depends(require_admin)):
    return vectordb.health()


@app.post("/admin/api/vectordb/documents")
async def vectordb_add_document(payload: dict, _: str = Depends(require_admin)):
    collection = (payload.get("collection") or "").strip()
    text = (payload.get("text") or "").strip()
    source = (payload.get("source") or "manual_text").strip()
    size = int(payload.get("size") or 500)
    overlap = int(payload.get("overlap") or 80)
    if not collection or not text:
        raise HTTPException(400, "collection과 text는 필수입니다.")
    try:
        res = vectordb.add_document(collection, text, source=source, size=size, overlap=overlap)
        return {"ok": True, **res}
    except Exception as e:
        raise HTTPException(502, f"등록 실패: {e}")


@app.post("/admin/api/vectordb/upload")
async def vectordb_upload(file: UploadFile = File(...),
                          collection: str = Form(""),
                          size: int = Form(500), overlap: int = Form(80),
                          _: str = Depends(require_admin)):
    collection = (collection or "").strip()
    if not collection:
        raise HTTPException(400, "collection은 필수입니다.")
    raw = await file.read()
    text = _extract_text(file.filename, raw)
    if not text.strip():
        raise HTTPException(400, "파일에서 추출된 텍스트가 없습니다.")
    try:
        res = vectordb.add_document(collection, text, source=file.filename,
                                    size=int(size), overlap=int(overlap))
        return {"ok": True, "filename": file.filename, **res}
    except Exception as e:
        raise HTTPException(502, f"등록 실패: {e}")


@app.get("/admin/api/vectordb/docs")
def vectordb_docs(collection: str, _: str = Depends(require_admin)):
    try:
        return {"documents": vectordb.list_documents(collection)}
    except Exception as e:
        raise HTTPException(502, f"문서 목록 조회 실패: {e}")


@app.get("/admin/api/vectordb/docs/chunks")
def vectordb_doc_chunks(collection: str, source: str, _: str = Depends(require_admin)):
    try:
        return {"chunks": vectordb.get_document_chunks(collection, source)}
    except Exception as e:
        raise HTTPException(502, f"문서 열람 실패: {e}")


@app.delete("/admin/api/vectordb/docs")
def vectordb_doc_delete(collection: str, source: str, _: str = Depends(require_admin)):
    try:
        return {"ok": vectordb.delete_document(collection, source)}
    except Exception as e:
        raise HTTPException(502, f"문서 삭제 실패: {e}")


@app.post("/admin/api/vectordb/search")
async def vectordb_search(payload: dict, _: str = Depends(require_admin)):
    collection = (payload.get("collection") or "").strip()
    query = (payload.get("query") or "").strip()
    k = int(payload.get("k") or 5)
    if not collection or not query:
        raise HTTPException(400, "collection과 query는 필수입니다.")
    try:
        return {"results": vectordb.search(collection, query, k)}
    except Exception as e:
        raise HTTPException(502, f"검색 실패: {e}")


@app.delete("/admin/api/vectordb/collections/{name}")
def vectordb_delete(name: str, _: str = Depends(require_admin)):
    try:
        vectordb.delete_collection(name)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(502, f"삭제 실패: {e}")


# ----------------------------- 관리자 페이지 -----------------------------

_ADMIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>엑큐(XCU) 관리자 콘솔</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         background:#0c0d13; color:#e8e8ef; }
  header { padding:16px 24px; background:linear-gradient(180deg,#15161f,#101119); border-bottom:1px solid #23253a;
           display:flex; align-items:center; gap:12px; }
  header h1 { font-size:18px; margin:0; }
  .wrap { display:flex; flex-direction:column; gap:16px; padding:16px 24px; }
  .card { background:#14151e; border:1px solid #23253a; border-radius:14px; padding:16px; }
  .card h2 { margin:0 0 12px; font-size:15px; color:#9aa4b2; display:flex; align-items:center; gap:8px; }
  .users { width:100%; }
  .sessions { width:100%; }
  .vectordb { width:100%; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:9px 10px; border-bottom:1px solid #20223a; }
  th { color:#7d8694; font-weight:600; }
  tr.clickable:hover { background:#1a1c2b; cursor:pointer; }
  .badge { font-size:11px; padding:2px 8px; border-radius:999px; background:#262a40; }
  .badge.admin { background:#3a2f12; color:#f0c674; }
  .pill { font-size:11px; padding:2px 8px; border-radius:999px; background:#2a2410; color:#f0c674; }
  input, select, textarea { background:#0c0d13; border:1px solid #2c2f48; color:#e8e8ef;
                  border-radius:8px; padding:7px 9px; font-size:13px; font-family:inherit; }
  textarea { width:100%; min-height:90px; resize:vertical; }
  button { background:linear-gradient(135deg,#6d5cf0,#9b5cf0); color:#fff; border:0; border-radius:8px; padding:7px 13px;
           font-size:13px; cursor:pointer; font-weight:600; transition:transform .12s ease, filter .2s ease; }
  button:hover { filter:brightness(1.08); transform:translateY(-1px); }
  button.danger { background:#2a1922; color:#ff8e9b; border:1px solid #4a2230; }
  button:disabled { opacity:.5; cursor:not-allowed; transform:none; }
  .row { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; align-items:center; }
  .field { display:flex; flex-direction:column; gap:6px; margin-top:10px; }
  .field label { font-size:12px; color:#7d8694; }
  .msgs { max-height:60vh; overflow:auto; }
  .msg { padding:10px 12px; border-radius:8px; margin-bottom:8px; white-space:pre-wrap;
         font-size:13px; line-height:1.5; }
  .msg.user { background:#1a1f33; }
  .msg.assistant { background:#171a2a; border:1px solid #23253a; }
  .msg .who { font-size:11px; color:#7d8694; margin-bottom:4px; }
  .muted { color:#7d8694; font-size:12px; }
  .toolbar { display:flex; align-items:center; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
  .toolbar .search { flex:1; min-width:160px; }
  .toolbar .count { color:#7d8694; font-size:12px; white-space:nowrap; }
  .pager { display:flex; align-items:center; gap:8px; justify-content:flex-end; margin-top:10px; }
  .pager button { background:#262a40; color:#e8e8ef; padding:5px 11px; font-weight:600; }
  .pager button:hover:not(:disabled) { filter:brightness(1.2); transform:none; }
  .pager .pageinfo { color:#7d8694; font-size:12px; min-width:78px; text-align:center; }
  .hit { background:#171a2a; border:1px solid #23253a; border-radius:8px; padding:9px 11px; margin-bottom:7px; font-size:13px; line-height:1.5; }
  .hit .meta { font-size:11px; color:#7d8694; margin-bottom:4px; display:flex; gap:10px; }
  .hit .score { color:#8b7cff; font-weight:600; }
  .pill.ok { background:#13301f; color:#79e0a8; }
  .pill.bad { background:#301317; color:#ff8e9b; }
  .notice { margin-top:10px; padding:8px 10px; border-radius:8px; background:#161a2a; border:1px dashed #34406a; color:#9fb0d6; font-size:12px; }
  .modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.62); display:none;
                   align-items:center; justify-content:center; z-index:1000; padding:24px; }
  .modal-overlay.open { display:flex; }
  .modal { background:#14151e; border:1px solid #23253a; border-radius:14px;
           width:min(860px,94vw); max-height:86vh; display:flex; flex-direction:column;
           box-shadow:0 24px 70px rgba(0,0,0,.55); }
  .modal-head { display:flex; align-items:center; gap:10px; padding:14px 16px; border-bottom:1px solid #23253a; }
  .modal-head .title { font-weight:600; font-size:14px; }
  .modal-head .badge-ro { font-size:11px; padding:2px 8px; border-radius:999px; background:#262a40; color:#9aa4b2; }
  .modal-close { margin-left:auto; background:#262a40; color:#e8e8ef; border:0; border-radius:8px;
                 padding:6px 11px; cursor:pointer; font-size:14px; font-weight:600; }
  .modal-close:hover { filter:brightness(1.15); }
  .modal .msgs { padding:16px; overflow:auto; max-height:none; }
</style>
</head>
<body>
<header>
  <span style="display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#8b7cff,#a66bff);color:#0e0f16;font-weight:800;font-size:15px;">X</span>
  <h1>엑큐 <span style="color:#8b7cff;">관리자 콘솔</span></h1>
  <span class="muted" style="margin-left:auto;">사용자 관리 · 세션 열람 · 벡터 DB</span>
</header>
<div class="wrap">
  <div class="card users">
    <h2>사용자 관리</h2>
    <div class="toolbar">
      <input id="userSearch" class="search" placeholder="🔎 아이디·이름 검색" oninput="onUserSearch()"/>
      <span class="count" id="userCount"></span>
    </div>
    <table id="userTable"><thead>
      <tr><th>아이디</th><th>이름</th><th>권한</th><th></th></tr>
    </thead><tbody></tbody></table>
    <div class="pager">
      <button id="userPrev" onclick="changeUserPage(-1)">◀ 이전</button>
      <span class="pageinfo" id="userPageInfo"></span>
      <button id="userNext" onclick="changeUserPage(1)">다음 ▶</button>
    </div>
    <div class="row">
      <input id="nu_id" placeholder="아이디" size="10"/>
      <input id="nu_name" placeholder="이름" size="8"/>
      <input id="nu_pw" placeholder="비밀번호" type="password" size="10"/>
      <select id="nu_role"><option value="user">user</option><option value="admin">admin</option></select>
      <button onclick="createUser()">추가</button>
    </div>
  </div>

  <div class="card sessions">
    <h2>세션(대화) 열람</h2>
    <div class="toolbar">
      <input id="threadSearch" class="search" placeholder="🔎 사용자·제목 검색" oninput="onThreadSearch()"/>
      <span class="count" id="threadCount"></span>
    </div>
    <table id="threadTable"><thead>
      <tr><th>사용자</th><th>제목</th><th>메시지</th><th>생성</th></tr>
    </thead><tbody></tbody></table>
    <div class="pager">
      <button id="threadPrev" onclick="changeThreadPage(-1)">◀ 이전</button>
      <span class="pageinfo" id="threadPageInfo"></span>
      <button id="threadNext" onclick="changeThreadPage(1)">다음 ▶</button>
    </div>
  </div>

  <div class="card vectordb">
    <h2>벡터 DB 문서 <span class="pill" id="vc_status">상태 확인중…</span></h2>
    <div class="row" style="margin-top:0;">
      <select id="vc_collection" style="min-width:170px;" onchange="loadVecDocs()"><option value="">(컬렉션 선택)</option></select>
      <input id="vc_new" placeholder="새 컬렉션명 (영문·숫자, 예: company_docs)" size="18" title="영문/숫자로 시작·끝나는 3자 이상. 허용: 영문·숫자·. _ - (한글·공백 불가)"/>
      <button onclick="refreshCollections()" style="background:#262a40;">↻ 새로고침</button>
      <span class="muted">청크</span>
      <input id="vc_size" type="number" value="500" min="100" step="50" size="5" title="청크 크기(자)" style="width:72px;"/>
      <span class="muted">겹침</span>
      <input id="vc_overlap" type="number" value="80" min="0" step="10" size="4" title="청크 겹침(자)" style="width:64px;"/>
    </div>

    <div class="field">
      <label>① 파일 업로드 (txt · md · csv · log · json · pdf · docx · pptx · xlsx)</label>
      <div class="row" style="margin-top:0;">
        <input id="vc_file" type="file" accept=".txt,.md,.csv,.log,.json,.pdf,.docx,.pptx,.xlsx"/>
        <button onclick="uploadVecFile()">📎 파일 등록</button>
      </div>
    </div>

    <div class="field">
      <label>② 또는 텍스트 직접 입력</label>
      <textarea id="vc_text" placeholder="임베딩하여 추가할 문서 텍스트를 붙여넣으세요..."></textarea>
    </div>
    <div class="row">
      <button id="vc_btn" onclick="addVecDoc()">＋ 텍스트 등록</button>
      <span class="muted">청킹 → bge-m3 임베딩 → ChromaDB 적재</span>
    </div>
    <div id="vc_result" class="muted" style="margin-top:10px;"></div>

    <div style="border-top:1px solid #20223a; margin:14px 0 0;"></div>
    <div class="field">
      <label>📚 등록된 문서 <span class="muted" id="vc_doccount"></span></label>
      <table id="vc_doctable"><thead>
        <tr><th>출처(문서)</th><th>청크</th><th>등록일</th><th></th></tr>
      </thead><tbody></tbody></table>
    </div>

    <div style="border-top:1px solid #20223a; margin:14px 0 0;"></div>
    <div class="field">
      <label>🔎 문서 검색 (선택한 컬렉션 내)</label>
      <div class="row" style="margin-top:0;">
        <input id="vc_q" class="search" placeholder="검색어를 입력하세요" style="flex:1;min-width:160px;"
               onkeydown="if(event.key==='Enter')searchVec()"/>
        <input id="vc_k" type="number" value="5" min="1" max="20" size="3" title="결과 수" style="width:64px;"/>
        <button onclick="searchVec()">검색</button>
      </div>
    </div>
    <div id="vc_search_result" style="margin-top:8px;"></div>
  </div>
</div>

<div id="modalOverlay" class="modal-overlay" onclick="closeModalBg(event)">
  <div class="modal">
    <div class="modal-head">
      <span class="title" id="modalTitle">대화</span>
      <span class="badge-ro">읽기 전용</span>
      <button class="modal-close" onclick="closeModal()">✕ 닫기</button>
    </div>
    <div id="modalBody" class="msgs"></div>
  </div>
</div>
<script>
async function api(path, opts) {
  const r = await fetch(path, opts || {});
  if (!r.ok) { const e = await r.json().catch(function(){return {detail:r.statusText};}); throw new Error(e.detail || r.statusText); }
  return r.json();
}
var PAGE_SIZE = 10;
var allUsers = [], userQuery = "", userPage = 1;
function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g, function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
async function loadUsers() {
  const data = await api("/admin/api/users");
  allUsers = data.users || [];
  renderUsers();
}
function filteredUsers() {
  const q = userQuery.trim().toLowerCase();
  if (!q) return allUsers;
  return allUsers.filter(function(u){
    return (u.identifier||"").toLowerCase().indexOf(q) >= 0
        || (u.display_name||"").toLowerCase().indexOf(q) >= 0;
  });
}
function renderUsers() {
  const list = filteredUsers();
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  if (userPage > pages) userPage = pages;
  const slice = list.slice((userPage-1)*PAGE_SIZE, userPage*PAGE_SIZE);
  const tb = document.querySelector("#userTable tbody"); tb.innerHTML = "";
  slice.forEach(function(u) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td>"+esc(u.identifier)+"</td><td>"+esc(u.display_name)+"</td>"+
      "<td><span class='badge "+u.role+"'>"+u.role+"</span></td>"+
      "<td><button class='danger'>삭제</button></td>";
    tr.querySelector("button").onclick = function(){ delUser(u.identifier); };
    tb.appendChild(tr);
  });
  if (!slice.length) tb.innerHTML = "<tr><td colspan='4' class='muted'>"+(userQuery?"검색 결과가 없습니다.":"사용자가 없습니다.")+"</td></tr>";
  document.getElementById("userCount").textContent = "총 "+list.length+"명"+(userQuery?" (검색됨)":"");
  document.getElementById("userPageInfo").textContent = userPage+" / "+pages;
  document.getElementById("userPrev").disabled = userPage <= 1;
  document.getElementById("userNext").disabled = userPage >= pages;
}
function onUserSearch() { userQuery = document.getElementById("userSearch").value; userPage = 1; renderUsers(); }
function changeUserPage(d) { userPage += d; renderUsers(); }
async function createUser() {
  const body = { identifier: nu_id.value.trim(), display_name: nu_name.value.trim(),
    password: nu_pw.value, role: nu_role.value };
  if (!body.identifier || !body.password) { alert("아이디와 비밀번호를 입력하세요."); return; }
  try { await api("/admin/api/users", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
    nu_id.value=nu_name.value=nu_pw.value=""; loadUsers();
  } catch(e){ alert("실패: "+e.message); }
}
async function delUser(id) {
  if (!confirm(id+" 계정을 삭제할까요?")) return;
  try { await api("/admin/api/users/"+encodeURIComponent(id), {method:"DELETE"}); loadUsers(); }
  catch(e){ alert("실패: "+e.message); }
}
var allThreads = [], threadQuery = "", threadPage = 1;
async function loadThreads() {
  const data = await api("/admin/api/threads");
  allThreads = data.threads || [];
  renderThreads();
}
function filteredThreads() {
  const q = threadQuery.trim().toLowerCase();
  if (!q) return allThreads;
  return allThreads.filter(function(t){
    return (t.user||"").toLowerCase().indexOf(q) >= 0
        || (t.name||"").toLowerCase().indexOf(q) >= 0;
  });
}
function renderThreads() {
  const list = filteredThreads();
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  if (threadPage > pages) threadPage = pages;
  const slice = list.slice((threadPage-1)*PAGE_SIZE, threadPage*PAGE_SIZE);
  const tb = document.querySelector("#threadTable tbody"); tb.innerHTML = "";
  slice.forEach(function(t) {
    const tr = document.createElement("tr"); tr.className="clickable";
    tr.innerHTML = "<td>"+esc(t.user||"?")+"</td><td>"+esc(t.name||"(제목없음)")+"</td>"+
      "<td>"+t.messages+"</td><td class='muted'>"+esc((t.created_at||"").slice(0,19).replace("T"," "))+"</td>";
    tr.onclick = function(){ loadMessages(t.id, t); };
    tb.appendChild(tr);
  });
  if (!slice.length) tb.innerHTML = "<tr><td colspan='4' class='muted'>"+(threadQuery?"검색 결과가 없습니다.":"세션이 없습니다.")+"</td></tr>";
  document.getElementById("threadCount").textContent = "총 "+list.length+"개"+(threadQuery?" (검색됨)":"");
  document.getElementById("threadPageInfo").textContent = threadPage+" / "+pages;
  document.getElementById("threadPrev").disabled = threadPage <= 1;
  document.getElementById("threadNext").disabled = threadPage >= pages;
}
function onThreadSearch() { threadQuery = document.getElementById("threadSearch").value; threadPage = 1; renderThreads(); }
function changeThreadPage(d) { threadPage += d; renderThreads(); }
async function loadMessages(id, t) {
  const body = document.getElementById("modalBody");
  document.getElementById("modalTitle").textContent = (t.user||"?") + " / " + (t.name||"(제목없음)");
  body.innerHTML = "<div class='muted'>불러오는 중...</div>";
  openModal();
  const data = await api("/admin/api/threads/"+encodeURIComponent(id));
  body.innerHTML = "<div class='muted' style='margin-bottom:8px;'>"+data.messages.length+" 메시지</div>";
  data.messages.forEach(function(m) {
    const d = document.createElement("div"); d.className = "msg "+m.role;
    const who = document.createElement("div"); who.className="who";
    who.textContent = m.role==="user" ? "🧑 사용자" : "🤖 어시스턴트";
    d.appendChild(who); d.appendChild(document.createTextNode(m.content));
    body.appendChild(d);
  });
  if (!data.messages.length) body.innerHTML += "<div class='muted'>메시지가 없습니다.</div>";
}
function openModal(){ document.getElementById("modalOverlay").classList.add("open"); }
function closeModal(){ document.getElementById("modalOverlay").classList.remove("open"); }
function closeModalBg(e){ if (e.target.id === "modalOverlay") closeModal(); }
document.addEventListener("keydown", function(e){ if (e.key === "Escape") closeModal(); });
function vcTargetCollection() {
  return (document.getElementById("vc_new").value.trim()) || document.getElementById("vc_collection").value;
}
function vcChunkParams() {
  return { size: parseInt(document.getElementById("vc_size").value||"500",10),
           overlap: parseInt(document.getElementById("vc_overlap").value||"80",10) };
}
async function refreshCollections() {
  const sel = document.getElementById("vc_collection");
  const status = document.getElementById("vc_status");
  try {
    const data = await api("/admin/api/vectordb/collections");
    const cols = data.collections || [];
    const cur = sel.value;
    sel.innerHTML = "<option value=''>(컬렉션 선택)</option>" + cols.map(function(c){
      return "<option value='"+esc(c.name)+"'>"+esc(c.name)+" ("+(c.count==null?"?":c.count)+")</option>";
    }).join("");
    if (cur) sel.value = cur;
    status.className = "pill ok"; status.textContent = "연결됨 · "+cols.length+"개 컬렉션";
  } catch(e){
    status.className = "pill bad"; status.textContent = "ChromaDB 미연결";
  }
}
async function addVecDoc() {
  const collection = vcTargetCollection();
  const text = document.getElementById("vc_text").value.trim();
  const out = document.getElementById("vc_result");
  if (!collection || !text) { out.textContent = "컬렉션(선택 또는 새 이름)과 문서 내용을 입력하세요."; return; }
  const cp = vcChunkParams();
  out.textContent = "⏳ 청킹·임베딩·적재 중...";
  try {
    const data = await api("/admin/api/vectordb/documents", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({collection:collection, text:text, size:cp.size, overlap:cp.overlap})});
    out.textContent = "✅ '"+data.collection+"'에 "+data.chunks+"개 청크 등록 완료";
    document.getElementById("vc_text").value=""; document.getElementById("vc_new").value="";
    await refreshCollections();
    document.getElementById("vc_collection").value = data.collection; loadVecDocs();
  } catch(e){ out.textContent = "❌ 실패: " + e.message; }
}
async function uploadVecFile() {
  const collection = vcTargetCollection();
  const f = document.getElementById("vc_file").files[0];
  const out = document.getElementById("vc_result");
  if (!collection) { out.textContent = "컬렉션(선택 또는 새 이름)을 지정하세요."; return; }
  if (!f) { out.textContent = "업로드할 파일을 선택하세요."; return; }
  const cp = vcChunkParams();
  const fd = new FormData();
  fd.append("file", f); fd.append("collection", collection);
  fd.append("size", cp.size); fd.append("overlap", cp.overlap);
  out.textContent = "⏳ '"+f.name+"' 업로드·청킹·임베딩 중...";
  try {
    const data = await api("/admin/api/vectordb/upload", {method:"POST", body:fd});
    out.textContent = "✅ '"+data.filename+"' → '"+data.collection+"'에 "+data.chunks+"개 청크 등록 완료";
    document.getElementById("vc_file").value=""; document.getElementById("vc_new").value="";
    await refreshCollections();
    document.getElementById("vc_collection").value = data.collection; loadVecDocs();
  } catch(e){ out.textContent = "❌ 실패: " + e.message; }
}
async function loadVecDocs() {
  const collection = document.getElementById("vc_collection").value;
  const tb = document.querySelector("#vc_doctable tbody");
  const cnt = document.getElementById("vc_doccount");
  tb.innerHTML = ""; cnt.textContent = "";
  if (!collection) { tb.innerHTML = "<tr><td colspan='4' class='muted'>컬렉션을 선택하세요.</td></tr>"; return; }
  tb.innerHTML = "<tr><td colspan='4' class='muted'>불러오는 중...</td></tr>";
  try {
    const data = await api("/admin/api/vectordb/docs?collection="+encodeURIComponent(collection));
    const docs = data.documents || [];
    cnt.textContent = "· "+docs.length+"건";
    if (!docs.length) { tb.innerHTML = "<tr><td colspan='4' class='muted'>등록된 문서가 없습니다.</td></tr>"; return; }
    tb.innerHTML = "";
    docs.forEach(function(d){
      const tr = document.createElement("tr");
      tr.innerHTML = "<td>"+esc(d.source)+"</td><td>"+d.chunks+"</td>"+
        "<td class='muted'>"+esc((d.added_at||"").replace("T"," "))+"</td>"+
        "<td style='white-space:nowrap;'><button style='background:#262a40;'>보기</button> "+
        "<button class='danger'>삭제</button></td>";
      const btns = tr.querySelectorAll("button");
      btns[0].onclick = function(){ viewVecDoc(collection, d.source); };
      btns[1].onclick = function(){ delVecDoc(collection, d.source); };
      tb.appendChild(tr);
    });
  } catch(e){ tb.innerHTML = "<tr><td colspan='4' class='muted'>실패: "+esc(e.message)+"</td></tr>"; }
}
async function viewVecDoc(collection, source) {
  const body = document.getElementById("modalBody");
  document.getElementById("modalTitle").textContent = collection + " / " + source;
  body.innerHTML = "<div class='muted'>불러오는 중...</div>"; openModal();
  try {
    const data = await api("/admin/api/vectordb/docs/chunks?collection="+encodeURIComponent(collection)+"&source="+encodeURIComponent(source));
    const chunks = data.chunks || [];
    body.innerHTML = "<div class='muted' style='margin-bottom:8px;'>"+chunks.length+" 청크</div>";
    chunks.forEach(function(c){
      const d = document.createElement("div"); d.className = "msg assistant";
      const who = document.createElement("div"); who.className="who"; who.textContent = "청크 #"+c.chunk;
      d.appendChild(who); d.appendChild(document.createTextNode(c.text));
      body.appendChild(d);
    });
    if (!chunks.length) body.innerHTML += "<div class='muted'>청크가 없습니다.</div>";
  } catch(e){ body.innerHTML = "<div class='muted'>실패: "+esc(e.message)+"</div>"; }
}
async function delVecDoc(collection, source) {
  if (!confirm("'"+source+"' 문서를 삭제할까요? (청크 전체 삭제)")) return;
  try {
    await api("/admin/api/vectordb/docs?collection="+encodeURIComponent(collection)+"&source="+encodeURIComponent(source), {method:"DELETE"});
    loadVecDocs(); refreshCollections();
  } catch(e){ alert("삭제 실패: "+e.message); }
}
async function searchVec() {
  const collection = document.getElementById("vc_collection").value;
  const query = document.getElementById("vc_q").value.trim();
  const k = parseInt(document.getElementById("vc_k").value||"5",10);
  const box = document.getElementById("vc_search_result");
  if (!collection) { box.innerHTML = "<div class='muted'>먼저 컬렉션을 선택하세요.</div>"; return; }
  if (!query) { box.innerHTML = "<div class='muted'>검색어를 입력하세요.</div>"; return; }
  box.innerHTML = "<div class='muted'>검색 중...</div>";
  try {
    const data = await api("/admin/api/vectordb/search", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({collection:collection, query:query, k:k})});
    const hits = data.results || [];
    if (!hits.length) { box.innerHTML = "<div class='muted'>결과가 없습니다.</div>"; return; }
    box.innerHTML = hits.map(function(h){
      return "<div class='hit'><div class='meta'><span class='score'>유사도 "+(h.score==null?"-":h.score)+
        "</span><span>출처: "+esc(h.source||"-")+(h.chunk==null?"":" #"+h.chunk)+"</span></div>"+esc(h.text)+"</div>";
    }).join("");
  } catch(e){ box.innerHTML = "<div class='pill bad' style='display:inline-block;'>실패: "+esc(e.message)+"</div>"; }
}
loadUsers(); loadThreads(); refreshCollections();
setInterval(loadThreads, 15000);
</script>
</body></html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_page(_: str = Depends(require_admin)):
    return HTMLResponse(_ADMIN_HTML)


# ---------------------------------------------------------------------------
# Chainlit SPA 카탈올 라우트(/{full_path:path})보다 우리 라우트가 먼저
# 매칭되도록 /admin · /api 라우트를 라우터 맨 앞으로 이동시킨다.
# ---------------------------------------------------------------------------
def _prioritize_custom_routes() -> None:
    routes = app.router.routes
    custom = [r for r in routes
              if getattr(r, "path", "").startswith("/admin")
              or getattr(r, "path", "").startswith("/api/")]
    for r in custom:
        routes.remove(r)
    for r in reversed(custom):
        routes.insert(0, r)


_prioritize_custom_routes()
