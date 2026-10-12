from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse
from .deps import container_of
from .errors import APIError
from .sse import sse_response

router = APIRouter(prefix="/api", tags=["chat"])


def _validate(request: Request, body: ChatRequest) -> int:
    c = container_of(request)
    if len(body.question) > c.settings.max_question_chars:
        raise APIError(422, "question_too_long", f"Questions are limited to {c.settings.max_question_chars} characters.")
    c.rag.check_documents(body.document_ids)
    return c.rag.resolve_k(body.k)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Answer a question from the selected documents (blocking)."""
    k = _validate(request, body)
    return container_of(request).rag.answer(body.question, body.document_ids, k)


@router.post("/chat/stream")
def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """
    Same as /api/chat, streamed as server-sent events:
    `retrieval` (retrieved chunks) -> `token`* -> `done` (full ChatResponse) | `error`.
    Closing the connection stops generation.
    """
    k = _validate(request, body)
    rag = container_of(request).rag

    def work(emit, should_stop):
        def on_retrieved(chunks, retrieval_ms):
            emit("retrieval", {"retrieved": [c.model_dump() for c in chunks], "retrieval_ms": round(retrieval_ms, 2)})

        response = rag.answer(
            body.question,
            body.document_ids,
            k,
            on_retrieved=on_retrieved,
            on_token=lambda text: emit("token", {"text": text}),
            should_stop=should_stop,
        )
        emit("done", response.model_dump())

    return sse_response(work)
