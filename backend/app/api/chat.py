from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse
from ..storage.metadata_store import MetadataStore, now_iso
from .deps import container_of
from .errors import APIError
from .sse import sse_response

router = APIRouter(prefix="/api", tags=["chat"])

# How much prior conversation to feed back into the prompt as memory for follow-up questions.
_HISTORY_TURNS = 3
_HISTORY_ANSWER_CHARS = 1500


def _validate(request: Request, body: ChatRequest) -> int:
    c = container_of(request)
    if len(body.question) > c.settings.max_question_chars:
        raise APIError(422, "question_too_long", f"Questions are limited to {c.settings.max_question_chars} characters.")
    c.rag.check_documents(body.document_ids)
    return c.rag.resolve_k(body.k)


def _recent_history(store: MetadataStore, document_ids: list[str]) -> list[tuple[str, str]]:
    """Prior (question, answer) pairs from this document-selection's saved conversation, oldest first."""
    conv = store.get_conversation(document_ids)
    if not conv:
        return []
    done = [t for t in conv["turns"] if t["status"] == "done" and t.get("response")]
    return [(t["question"], t["response"]["answer"][:_HISTORY_ANSWER_CHARS]) for t in done[-_HISTORY_TURNS:]]


def _save_turn(store: MetadataStore, document_ids: list[str], question: str, k: int, response: ChatResponse) -> None:
    store.append_turn(
        document_ids,
        {
            "id": str(uuid.uuid4()),
            "question": question,
            "k": k,
            "status": "cancelled" if response.cancelled else "done",
            "response": response.model_dump(),
            "created_at": now_iso(),
        },
    )


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Answer a question from the selected documents (blocking)."""
    k = _validate(request, body)
    c = container_of(request)
    history = _recent_history(c.store, body.document_ids)
    response = c.rag.answer(body.question, body.document_ids, k, history=history)
    _save_turn(c.store, body.document_ids, body.question, k, response)
    return response


@router.post("/chat/stream")
def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """
    Same as /api/chat, streamed as server-sent events:
    `retrieval` (retrieved chunks) -> `token`* -> `done` (full ChatResponse) | `error`.
    Closing the connection stops generation.
    """
    k = _validate(request, body)
    c = container_of(request)
    history = _recent_history(c.store, body.document_ids)

    def work(emit, should_stop):
        def on_retrieved(chunks, retrieval_ms):
            emit("retrieval", {"retrieved": [chunk.model_dump() for chunk in chunks], "retrieval_ms": round(retrieval_ms, 2)})

        response = c.rag.answer(
            body.question,
            body.document_ids,
            k,
            on_retrieved=on_retrieved,
            on_token=lambda text: emit("token", {"text": text}),
            should_stop=should_stop,
            history=history,
        )
        _save_turn(c.store, body.document_ids, body.question, k, response)
        emit("done", response.model_dump())

    return sse_response(work)
