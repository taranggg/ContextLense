"""
Document lifecycle: upload -> validate -> extract -> chunk -> embed -> index -> ready.

Processing runs on a single background worker so uploads return immediately
with a document id that the client polls.
"""
from __future__ import annotations

import logging
import re
import secrets
import threading
import unicodedata
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO, Optional

from ..config import Settings
from ..schemas import Chunk, DocumentInfo, DocumentStatus
from ..storage.document_files import DocumentFiles, is_valid_document_id, write_jsonl
from ..storage.metadata_store import MetadataStore
from .chunking_service import chunk_pages
from .embedding_service import Embedder, EmbeddingUnavailableError
from .preprocessing_service import PDFValidationError, extract_pages, inspect_pdf, validate_pdf_upload
from .retrieval_service import RetrievalService

logger = logging.getLogger("contextlens.documents")

_COPY_BUFFER = 1024 * 1024


class DocumentNotFoundError(LookupError):
    pass


class UploadTooLargeError(Exception):
    def __init__(self, limit_mb: int):
        super().__init__(f"The file is larger than the {limit_mb} MB limit.")
        self.limit_mb = limit_mb


class _Deleted(Exception):
    """Raised inside the pipeline when the document was deleted mid-processing."""


def display_filename(name: Optional[str]) -> str:
    """A safe label for the UI. Never used as a filesystem path."""
    base = Path((name or "").replace("\\", "/")).name
    base = unicodedata.normalize("NFC", base)
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return (base or "document.pdf")[:200]


class DocumentService:
    def __init__(self, settings: Settings, store: MetadataStore, embedder: Embedder, retrieval: RetrievalService):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.retrieval = retrieval
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
        self._deleted: set[str] = set()
        self._deleted_lock = threading.Lock()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ queries

    def list(self) -> list[DocumentInfo]:
        return self.store.list_documents()

    def get(self, doc_id: str) -> DocumentInfo:
        doc = self.store.get_document(doc_id) if is_valid_document_id(doc_id) else None
        if doc is None:
            raise DocumentNotFoundError(doc_id)
        return doc

    def chunks(self, doc_id: str) -> list[Chunk]:
        self.get(doc_id)
        return self.retrieval.load_chunks(doc_id)

    # ------------------------------------------------------------------ upload

    def create_from_upload(
        self,
        filename: Optional[str],
        content_type: Optional[str],
        stream: BinaryIO,
        is_sample: bool = False,
        process_async: bool = True,
    ) -> DocumentInfo:
        doc_id = secrets.token_hex(8)
        files = DocumentFiles(self.settings.documents_dir, doc_id)
        files.create()
        try:
            head = stream.read(1024)
            validate_pdf_upload(filename, content_type, head)
            size = len(head)
            with open(files.source_pdf, "wb") as out:
                out.write(head)
                while True:
                    block = stream.read(_COPY_BUFFER)
                    if not block:
                        break
                    size += len(block)
                    if size > self.settings.max_upload_bytes:
                        raise UploadTooLargeError(self.settings.max_upload_mb)
                    out.write(block)
            inspect_pdf(files.source_pdf)
        except BaseException:
            files.remove_all()
            raise

        doc = self.store.create_document(doc_id, display_filename(filename), size, is_sample=is_sample)
        logger.info("Stored upload %s (%d bytes)", doc_id, size)
        if process_async:
            self._executor.submit(self._process_safely, doc_id)
        else:
            self._process_safely(doc_id)
        return self.store.get_document(doc_id) or doc

    def reprocess(self, doc_id: str) -> DocumentInfo:
        doc = self.get(doc_id)
        if doc.status not in (DocumentStatus.ready, DocumentStatus.failed):
            return doc
        self.store.update_document(doc_id, status=DocumentStatus.queued, error_code=None, error_message=None, warnings=[])
        self.retrieval.evict(doc_id)
        self._executor.submit(self._process_safely, doc_id)
        return self.get(doc_id)

    def submit(self, doc_id: str) -> Future:
        return self._executor.submit(self._process_safely, doc_id)

    # ------------------------------------------------------------------ delete

    def delete(self, doc_id: str) -> None:
        self.get(doc_id)
        with self._deleted_lock:
            self._deleted.add(doc_id)
        self.store.delete_document(doc_id)
        self.store.delete_comparisons_for_document(doc_id)
        self.retrieval.evict(doc_id)
        DocumentFiles(self.settings.documents_dir, doc_id).remove_all()
        logger.info("Deleted document %s and its derived data", doc_id)

    def _check_not_deleted(self, doc_id: str) -> None:
        with self._deleted_lock:
            if doc_id in self._deleted:
                raise _Deleted()

    # ------------------------------------------------------------------ pipeline

    def _set_status(self, doc_id: str, status: DocumentStatus, **fields) -> None:
        self._check_not_deleted(doc_id)
        self.store.update_document(doc_id, status=status, **fields)

    def _fail(self, doc_id: str, code: str, message: str) -> None:
        self.store.update_document(doc_id, status=DocumentStatus.failed, error_code=code, error_message=message)

    def _process_safely(self, doc_id: str) -> None:
        try:
            self._process(doc_id)
        except _Deleted:
            DocumentFiles(self.settings.documents_dir, doc_id).remove_all()
            logger.info("Document %s was deleted during processing", doc_id)
        except PDFValidationError as exc:
            self._fail(doc_id, exc.code, exc.message)
        except EmbeddingUnavailableError as exc:
            logger.error("Embedding failed for %s: %s", doc_id, exc)
            self._fail(doc_id, "embedding_unavailable", "The local embedding model could not be loaded, so the document was not indexed.")
        except Exception:
            logger.exception("Processing failed for %s", doc_id)
            self._fail(doc_id, "processing_error", "An unexpected error occurred while processing this document.")

    def _process(self, doc_id: str) -> None:
        doc = self.get(doc_id)
        files = DocumentFiles(self.settings.documents_dir, doc_id)
        files.clear_derived()
        self.retrieval.evict(doc_id)

        self._set_status(doc_id, DocumentStatus.extracting)
        pages = extract_pages(files.source_pdf, doc_id, doc.filename, self.settings.min_page_words)
        write_jsonl(files.pages, pages)
        with_text = sum(1 for p in pages if p.has_text)
        warnings: list[str] = []
        if with_text == 0:
            self._set_status(
                doc_id,
                DocumentStatus.failed,
                page_count=len(pages),
                pages_with_text=0,
                word_count=0,
                error_code="no_text",
                error_message=(
                    "No extractable text was found. This PDF appears to be scanned or image-only. "
                    "OCR is not implemented in ContextLens yet, so it cannot be searched."
                ),
            )
            return
        if with_text < len(pages):
            missing = len(pages) - with_text
            warnings.append(
                f"{missing} of {len(pages)} pages have no extractable text (possibly scanned images). "
                "They are not searchable because OCR is not implemented."
            )
        self._set_status(
            doc_id,
            DocumentStatus.chunking,
            page_count=len(pages),
            pages_with_text=with_text,
            word_count=sum(p.word_count for p in pages),
            warnings=warnings,
        )

        chunks = chunk_pages(pages, self.settings.chunk_size_words, self.settings.chunk_overlap_words)
        self._set_status(doc_id, DocumentStatus.embedding, chunk_count=len(chunks))

        vectors = self.embedder.encode([c.text for c in chunks])
        self._set_status(doc_id, DocumentStatus.indexing)

        self.retrieval.build_index(doc_id, chunks, vectors)
        self._set_status(
            doc_id,
            DocumentStatus.ready,
            embedding_model=self.embedder.model_name,
            chunk_size_words=self.settings.chunk_size_words,
            chunk_overlap_words=self.settings.chunk_overlap_words,
            error_code=None,
            error_message=None,
        )
        logger.info("Document %s ready: %d pages, %d chunks", doc_id, len(pages), len(chunks))

    # ------------------------------------------------------------------ samples

    def ingest_file(self, path: Path, is_sample: bool = True) -> DocumentInfo:
        """Synchronously ingest a local PDF (used for the bundled sample/benchmark documents)."""
        with open(path, "rb") as f:
            return self.create_from_upload(path.name, "application/pdf", f, is_sample=is_sample, process_async=False)

