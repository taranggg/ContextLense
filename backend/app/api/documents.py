from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ..schemas import ChunkPage, DocumentInfo, DocumentList
from .deps import container_of
from .errors import APIError

router = APIRouter(prefix="/api/documents", tags=["documents"])

_MULTIPART_OVERHEAD = 64 * 1024


@router.post("", status_code=202, response_model=DocumentInfo)
async def upload_document(request: Request) -> DocumentInfo:
    """Upload a PDF as multipart field `file`. Returns immediately; poll the document for its status."""
    c = container_of(request)
    limit = c.settings.max_upload_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + _MULTIPART_OVERHEAD:
        raise APIError(413, "file_too_large", f"The file is larger than the {c.settings.max_upload_mb} MB limit.")

    form = await request.form(max_files=1, max_fields=5)
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise APIError(400, "missing_file", "Attach a PDF in the 'file' field.")
    try:
        return await run_in_threadpool(
            c.documents.create_from_upload, upload.filename, upload.content_type, upload.file
        )
    finally:
        await upload.close()


@router.get("", response_model=DocumentList)
def list_documents(request: Request) -> DocumentList:
    return DocumentList(documents=container_of(request).documents.list())


@router.get("/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str, request: Request) -> DocumentInfo:
    return container_of(request).documents.get(document_id)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, request: Request) -> Response:
    container_of(request).documents.delete(document_id)
    return Response(status_code=204)


@router.post("/{document_id}/reprocess", status_code=202, response_model=DocumentInfo)
def reprocess_document(document_id: str, request: Request) -> DocumentInfo:
    return container_of(request).documents.reprocess(document_id)


@router.get("/{document_id}/chunks", response_model=ChunkPage)
def list_chunks(
    document_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ChunkPage:
    c = container_of(request)
    doc = c.documents.get(document_id)
    if doc.status.value != "ready":
        raise APIError(409, "document_not_ready", f"'{doc.filename}' is not ready yet (status: {doc.status.value}).")
    chunks = c.documents.chunks(document_id)
    return ChunkPage(
        document_id=document_id, total=len(chunks), offset=offset, limit=limit, chunks=chunks[offset : offset + limit]
    )
