from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import ComponentStatus, DocumentStatus, ReadinessResponse
from .deps import container_of

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness only: the API process is up. Says nothing about models; see /api/ready."""
    return {"status": "ok", "service": "contextlens-api"}


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request) -> ReadinessResponse:
    c = container_of(request)
    try:
        docs = c.store.list_documents()
        storage = ComponentStatus(status="ready", detail=f"{len(docs)} document(s) stored")
    except Exception:
        docs = []
        storage = ComponentStatus(status="error", detail="Metadata store is not readable.")

    emb_state, emb_detail = c.embedder.status()
    embedding = ComponentStatus(status=emb_state, detail=emb_detail)  # type: ignore[arg-type]
    llm = c.llm.status()
    documents_ready = sum(1 for d in docs if d.status == DocumentStatus.ready)

    return ReadinessResponse(
        ready=storage.status == "ready" and embedding.status in ("ready", "not_loaded") and llm.status == "ready",
        backend=ComponentStatus(status="ready"),
        storage=storage,
        embedding=embedding,
        llm=llm,
        documents_ready=documents_ready,
        limits={
            "max_upload_mb": c.settings.max_upload_mb,
            "default_top_k": c.settings.default_top_k,
            "research_k_values": list(c.settings.research_k_values),
            "max_question_chars": c.settings.max_question_chars,
        },
    )
