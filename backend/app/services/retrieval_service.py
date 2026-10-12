"""
Vector indexing and Top-K retrieval.

Each document has its own exact FAISS index (IndexFlatIP over normalised
vectors, so scores are cosine similarities). A query against several documents
searches each selected index and merges the results by score, which gives the
same ranking as one combined exact index. Unselected or deleted documents can
never appear in results because their indexes are never searched.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from ..schemas import Chunk, RetrievedChunk
from ..storage.document_files import DocumentFiles, read_jsonl, write_json, write_jsonl
from .embedding_service import Embedder

logger = logging.getLogger("contextlens.retrieval")


class IndexIntegrityError(RuntimeError):
    pass


class EmptyIndexError(RuntimeError):
    pass


@dataclass
class _LoadedIndex:
    index: faiss.Index
    chunks: list[Chunk]
    embedding_model: str


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    retrieval_ms: float


class RetrievalService:
    def __init__(self, documents_dir: Path, embedder: Embedder):
        self.documents_dir = documents_dir
        self.embedder = embedder
        self._cache: dict[str, _LoadedIndex] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ indexing

    def build_index(self, doc_id: str, chunks: list[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) != vectors.shape[0]:
            raise IndexIntegrityError(f"{len(chunks)} chunks but {vectors.shape[0]} vectors")
        files = DocumentFiles(self.documents_dir, doc_id)
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        write_jsonl(files.chunks, chunks)
        np.save(files.embeddings, vectors)
        faiss.write_index(index, str(files.index))
        write_json(
            files.index_meta,
            {
                "embedding_model": self.embedder.model_name,
                "dimension": int(vectors.shape[1]),
                "metric": "cosine (inner product of L2-normalised vectors)",
                "chunk_ids": [c.chunk_id for c in chunks],
            },
        )
        self.evict(doc_id)

    def evict(self, doc_id: str) -> None:
        with self._lock:
            self._cache.pop(doc_id, None)

    def _load(self, doc_id: str) -> _LoadedIndex:
        with self._lock:
            cached = self._cache.get(doc_id)
        if cached:
            return cached
        files = DocumentFiles(self.documents_dir, doc_id)
        if not files.index.exists() or not files.index_meta.exists():
            raise IndexIntegrityError(f"Index for document {doc_id} is missing.")
        meta = json.loads(files.index_meta.read_text(encoding="utf-8"))
        chunks = read_jsonl(files.chunks, Chunk)
        index = faiss.read_index(str(files.index))
        if index.ntotal != len(chunks) or meta.get("chunk_ids") != [c.chunk_id for c in chunks]:
            raise IndexIntegrityError(f"Index and chunk metadata for document {doc_id} are out of sync. Reprocess it.")
        loaded = _LoadedIndex(index=index, chunks=chunks, embedding_model=meta.get("embedding_model", ""))
        with self._lock:
            self._cache[doc_id] = loaded
        return loaded

    def load_chunks(self, doc_id: str) -> list[Chunk]:
        return self._load(doc_id).chunks

    # ------------------------------------------------------------------ retrieval

    def retrieve(self, query: str, document_ids: list[str], k: int = 5) -> RetrievalResult:
        """Top-k chunks across the given documents, ranked by cosine similarity."""
        if k < 1:
            raise ValueError("k must be >= 1")
        start = time.perf_counter()
        loaded = [(doc_id, self._load(doc_id)) for doc_id in dict.fromkeys(document_ids)]
        for doc_id, li in loaded:
            if li.embedding_model != self.embedder.model_name:
                raise IndexIntegrityError(
                    f"Document {doc_id} was indexed with '{li.embedding_model}' but the current embedding model is "
                    f"'{self.embedder.model_name}'. Reprocess the document."
                )
        if sum(li.index.ntotal for _, li in loaded) == 0:
            raise EmptyIndexError("The selected documents have no indexed text.")

        query_vec = self.embedder.encode([query])
        candidates: list[tuple[float, int, int, Chunk]] = []
        for order, (_, li) in enumerate(loaded):
            n = min(k, li.index.ntotal)
            if n == 0:
                continue
            scores, idxs = li.index.search(query_vec, n)
            for score, idx in zip(scores[0], idxs[0]):
                if idx >= 0:
                    candidates.append((float(score), order, int(idx), li.chunks[idx]))
        # Highest score first; ties broken deterministically by document order then chunk position.
        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))

        results = [
            RetrievedChunk(
                rank=rank,
                source_label=f"S{rank}",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                pages=chunk.pages,
                text=chunk.text,
                word_count=chunk.word_count,
                page_starts=chunk.page_starts,
                similarity=round(score, 6),
            )
            for rank, (score, _, _, chunk) in enumerate(candidates[:k], start=1)
        ]
        return RetrievalResult(chunks=results, retrieval_ms=(time.perf_counter() - start) * 1000)
