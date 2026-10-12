from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..container import Container
from ..schemas import Conversation, ConversationList, ConversationSummary, SavedTurn
from .deps import container_of
from .errors import APIError

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _split_ids(ids: str) -> list[str]:
    return [i for i in ids.split(",") if i]


def _document_names(c: Container, document_ids: list[str]) -> list[str]:
    names = []
    for doc_id in document_ids:
        doc = c.store.get_document(doc_id)
        names.append(doc.filename if doc else "Deleted document")
    return names


@router.get("", response_model=ConversationList)
def list_conversations(request: Request) -> ConversationList:
    c = container_of(request)
    summaries = [
        ConversationSummary(
            document_ids=conv["document_ids"],
            document_names=_document_names(c, conv["document_ids"]),
            title=conv["title"],
            turn_count=len(conv["turns"]),
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
        )
        for conv in c.store.list_conversations()
    ]
    return ConversationList(conversations=summaries)


@router.get("/{ids}", response_model=Conversation)
def get_conversation(ids: str, request: Request) -> Conversation:
    c = container_of(request)
    conv = c.store.get_conversation(_split_ids(ids))
    if not conv:
        raise APIError(404, "conversation_not_found", "No conversation for these documents yet.")
    return Conversation(
        document_ids=conv["document_ids"],
        document_names=_document_names(c, conv["document_ids"]),
        title=conv["title"],
        turns=[SavedTurn(**t) for t in conv["turns"]],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


@router.delete("/{ids}", status_code=204)
def delete_conversation(ids: str, request: Request) -> Response:
    container_of(request).store.delete_conversation(_split_ids(ids))
    return Response(status_code=204)
