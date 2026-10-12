"""Translate service exceptions into consistent, user-safe HTTP errors: {"error": {"code", "message"}}."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..services.document_service import DocumentNotFoundError, UploadTooLargeError
from ..services.embedding_service import EmbeddingUnavailableError
from ..services.llm_service import GenerationError, LLMUnavailableError
from ..services.preprocessing_service import PDFValidationError
from ..services.rag_service import DocumentsNotReadyError
from ..services.retrieval_service import EmptyIndexError, IndexIntegrityError

logger = logging.getLogger("contextlens.api")


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def describe(exc: Exception) -> tuple[int, str, str]:
    """(HTTP status, error code, user-facing message). Never exposes paths or stack traces."""
    if isinstance(exc, APIError):
        return exc.status, exc.code, exc.message
    if isinstance(exc, DocumentNotFoundError):
        return 404, "document_not_found", "Document not found."
    if isinstance(exc, UploadTooLargeError):
        return 413, "file_too_large", str(exc)
    if isinstance(exc, PDFValidationError):
        return (415 if exc.code in ("invalid_mime_type", "invalid_extension") else 400), exc.code, exc.message
    if isinstance(exc, DocumentsNotReadyError):
        return 409, exc.code, exc.message
    if isinstance(exc, EmptyIndexError):
        return 409, "empty_index", str(exc)
    if isinstance(exc, IndexIntegrityError):
        return 409, "index_error", str(exc)
    if isinstance(exc, LLMUnavailableError):
        return 503, exc.code, exc.message
    if isinstance(exc, EmbeddingUnavailableError):
        return 503, "embedding_unavailable", "The local embedding model is unavailable."
    if isinstance(exc, GenerationError):
        return 502, "generation_failed", "The local model failed while generating an answer. Please try again."
    if isinstance(exc, ValueError):
        return 422, "invalid_request", str(exc)
    logger.exception("Unhandled error", exc_info=exc)
    return 500, "internal_error", "Something went wrong on the server."


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    handled = (
        APIError,
        DocumentNotFoundError,
        UploadTooLargeError,
        PDFValidationError,
        DocumentsNotReadyError,
        EmptyIndexError,
        IndexIntegrityError,
        LLMUnavailableError,
        EmbeddingUnavailableError,
        GenerationError,
        ValueError,
    )

    async def handler(_: Request, exc: Exception) -> JSONResponse:
        status, code, message = describe(exc)
        return JSONResponse(status_code=status, content=error_body(code, message))

    for exc_type in handled:
        app.add_exception_handler(exc_type, handler)
