"""벡터 DB(ChromaDB) + 임베딩(Infinity bge-m3) 연동 헬퍼.

- 임베딩: Infinity 서버(OpenAI 호환 /embeddings)로 bge-m3 벡터 생성.
- 적재/검색: ChromaDB HttpClient. 청크 단위로 upsert, 질의는 query_embeddings 사용.
- 적재와 검색 모두 같은 Infinity 모델로 임베딩하므로 벡터 공간이 일치한다.

환경변수(없으면 compose 기본값):
  CHROMA_HOST(=chromadb) · CHROMA_PORT(=8000)
  EMBEDDING_URL(=http://embedding-server:7997) · EMBEDDING_MODEL(자동 감지)
"""
import hashlib
import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://embedding-server:7997").rstrip("/")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")  # 비우면 /models에서 자동 감지
# Infinity EF 재구성용 키 환경변수명. 값 자체는 Infinity가 무시(인증 없음).
# 이 이름의 env가 xcu·chroma-mcp 양쪽에 있어야 persist된 EF를 양쪽에서 재구성 가능.
OPENAI_KEY_ENV = os.getenv("VECTORDB_KEY_ENV", "CHROMA_OPENAI_API_KEY")
os.environ.setdefault(OPENAI_KEY_ENV, "dummy")

_client = None
_model_id_cache = None
_ef_cache = None


# ----------------------------- 임베딩 (Infinity) -----------------------------

def _model_id() -> str:
    """Infinity가 서빙 중인 모델 id를 1회 조회해 캐시(실패 시 기본값)."""
    global _model_id_cache
    if EMBEDDING_MODEL:
        return EMBEDDING_MODEL
    if _model_id_cache:
        return _model_id_cache
    try:
        r = requests.get(f"{EMBEDDING_URL}/models", timeout=10)
        r.raise_for_status()
        _model_id_cache = r.json()["data"][0]["id"]   # 성공 시에만 캐시
        return _model_id_cache
    except Exception as e:
        logger.warning(f"임베딩 모델 자동감지 실패({e}) → 임시 기본값(미캐시)")
        return "bge-m3"


def embed(texts: list[str]) -> list[list[float]]:
    """텍스트 목록을 Infinity bge-m3 벡터로 변환."""
    if not texts:
        return []
    r = requests.post(
        f"{EMBEDDING_URL}/embeddings",
        json={"model": _model_id(), "input": texts},
        timeout=120,
    )
    r.raise_for_status()
    data = sorted(r.json()["data"], key=lambda x: x["index"])
    return [d["embedding"] for d in data]


# ----------------------------- 청킹 -----------------------------

def chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    """문장/문단 경계를 우선해 size자 내외로 자르고 overlap만큼 겹친다."""
    text = (text or "").strip()
    if not text:
        return []
    size = max(100, int(size))
    overlap = max(0, min(int(overlap), size // 2))
    pieces = re.split(r"(?<=[.!?。！？\n])\s+", text)
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 1 <= size:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            if len(p) > size:                      # 한 조각이 너무 길면 강제 분할
                step = max(1, size - overlap)
                for i in range(0, len(p), step):
                    chunks.append(p[i:i + size])
                cur = ""
            else:
                cur = p
    if cur:
        chunks.append(cur)
    if overlap and len(chunks) > 1:                # 인접 청크 앞쪽에 직전 꼬리 덧붙임
        out = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            out.append((tail + " " + chunks[i]).strip())
        chunks = out
    return chunks


# ----------------------------- ChromaDB -----------------------------

def client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _client


def _ef():
    """컬렉션에 persist되는 임베딩 함수 = Infinity(OpenAI 호환) bge-m3.

    UI와 chroma-mcp가 같은 컬렉션을 열면 이 설정이 재구성되어
    양쪽 모두 동일한 Infinity bge-m3로 임베딩 → 검색 결과 일치.
    """
    global _ef_cache
    if _ef_cache is None:
        from chromadb.utils import embedding_functions as ef
        _ef_cache = ef.OpenAIEmbeddingFunction(
            api_base=EMBEDDING_URL,            # openai SDK가 /embeddings 를 붙여 호출
            model_name=_model_id(),
            api_key_env_var=OPENAI_KEY_ENV,
        )
    return _ef_cache


# ChromaDB 컬렉션명 규칙: 영문/숫자·'.'·'_'·'-' 만, 3~512자, 영숫자로 시작·끝.
_COLLECTION_INVALID_RE = re.compile(r"[^a-zA-Z0-9._-]")


def normalize_collection_name(name: str) -> str:
    """관리자가 입력한 컬렉션명을 ChromaDB 규칙에 맞게 정규화한다.

    - 공백류는 '-'로, 그 외 허용 외 문자는 제거(한글·특수문자 등).
    - 연속 구분자 축약, 시작/끝의 비영숫자 제거.
    - 정규화 후에도 규칙(3자 이상)을 못 맞추면 명확한 에러를 던진다.
    반환값이 곧 실제 생성/사용되는 컬렉션명이다.
    """
    raw = (name or "").strip()
    if not raw:
        raise ValueError("컬렉션명이 필요합니다.")
    s = re.sub(r"\s+", "-", raw)                 # 공백 → '-'
    s = _COLLECTION_INVALID_RE.sub("", s)        # 허용 외 문자(한글 등) 제거
    s = re.sub(r"([._-])[._-]+", r"\1", s)       # 연속 구분자 축약
    s = s.strip("._-")                           # 시작/끝은 영숫자
    if len(s) < 3:
        raise ValueError(
            f"컬렉션명 '{raw}'은(는) 사용할 수 없습니다. "
            "영문/숫자로 시작·끝나는 3자 이상이어야 하며, "
            "허용 문자는 영문·숫자·'.'·'_'·'-' 입니다(한글·공백 불가). "
            "예: company_docs, hr-policy-2026"
        )
    return s[:512]


def _collection(name: str):
    return client().get_or_create_collection(
        name=normalize_collection_name(name),
        metadata={"hnsw:space": "cosine"}, embedding_function=_ef()
    )


def list_collections() -> list[dict]:
    """컬렉션 이름 + 문서(청크) 수."""
    out = []
    for c in client().list_collections():
        name = getattr(c, "name", c)
        try:
            cnt = client().get_collection(name).count()
        except Exception:
            cnt = None
        out.append({"name": name, "count": cnt})
    return out


def add_document(collection: str, text: str, source: str = "",
                 size: int = 500, overlap: int = 80, extra: dict | None = None) -> dict:
    """문서를 청킹·임베딩해 컬렉션에 upsert. 반환: 등록 청크 수."""
    collection = normalize_collection_name(collection)  # 없으면 _collection이 생성
    chunks = chunk_text(text, size, overlap)
    if not chunks:
        raise ValueError("등록할 텍스트가 비어 있습니다.")
    src = (source or "doc").strip()
    base = hashlib.md5(src.encode("utf-8")).hexdigest()[:8]
    ids = [f"{src}::{base}::{i}" for i in range(len(chunks))]
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta = {"source": src, "added_at": ts}
    if extra:
        meta.update({k: v for k, v in extra.items()
                     if isinstance(v, (str, int, float, bool))})
    metadatas = [{**meta, "chunk": i} for i in range(len(chunks))]
    col = _collection(collection)  # 임베딩은 컬렉션 EF(Infinity)가 자동 수행
    col.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return {"collection": collection, "source": src, "chunks": len(chunks)}


def search(collection: str, query: str, k: int = 5) -> list[dict]:
    """질의를 임베딩해 컬렉션에서 유사 청크 top-k 반환."""
    collection = (collection or "").strip()
    query = (query or "").strip()
    if not collection or not query:
        raise ValueError("컬렉션과 검색어가 필요합니다.")
    res = _collection(collection).query(  # 질의 임베딩도 컬렉션 EF(Infinity)가 수행
        query_texts=[query], n_results=max(1, int(k)),
        include=["documents", "metadatas", "distances"],
    )
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else None
        out.append({
            "text": doc,
            "source": (meta or {}).get("source", ""),
            "chunk": (meta or {}).get("chunk"),
            "score": round(1 - dist, 4) if isinstance(dist, (int, float)) else None,
        })
    return out


def list_documents(collection: str) -> list[dict]:
    """컬렉션에 등록된 '원본 문서'(source) 목록 + 청크 수 + 등록일."""
    col = _collection(collection)
    got = col.get(include=["metadatas"])
    metas = got.get("metadatas") or []
    agg: dict[str, dict] = {}
    for m in metas:
        m = m or {}
        s = m.get("source", "(unknown)")
        e = agg.setdefault(s, {"source": s, "chunks": 0, "added_at": m.get("added_at")})
        e["chunks"] += 1
        if m.get("added_at") and not e.get("added_at"):
            e["added_at"] = m["added_at"]
    return sorted(agg.values(), key=lambda x: (x.get("added_at") or "", x["source"]), reverse=True)


def get_document_chunks(collection: str, source: str) -> list[dict]:
    """특정 원본 문서(source)의 청크 전체를 순서대로 반환."""
    col = _collection(collection)
    got = col.get(where={"source": source}, include=["documents", "metadatas"])
    docs = got.get("documents") or []
    metas = got.get("metadatas") or []
    rows = []
    for i, d in enumerate(docs):
        m = metas[i] if i < len(metas) else {}
        rows.append({"chunk": (m or {}).get("chunk", i), "text": d})
    rows.sort(key=lambda x: x["chunk"] if isinstance(x["chunk"], int) else 0)
    return rows


def delete_document(collection: str, source: str) -> bool:
    """특정 원본 문서(source)의 모든 청크 삭제."""
    _collection(collection).delete(where={"source": source})
    return True


def delete_collection(name: str) -> bool:
    client().delete_collection(name)
    return True


def health() -> dict:
    """Chroma / Infinity 연결 상태 점검."""
    st = {"chroma": False, "embedding": False, "model": None}
    try:
        client().heartbeat()
        st["chroma"] = True
    except Exception as e:
        st["chroma_error"] = str(e)
    try:
        st["model"] = _model_id()
        st["embedding"] = len(embed(["ping"])) == 1
    except Exception as e:
        st["embedding_error"] = str(e)
    return st
