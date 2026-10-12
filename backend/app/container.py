"""Wires services together. Tests inject small fakes for the embedder and LLM."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Settings
from .services.document_service import DocumentService
from .services.embedding_service import Embedder, SentenceTransformerEmbedder
from .services.experiment_service import ExperimentService
from .services.llm_service import LLMBackend, create_llm_backend
from .services.rag_service import RAGService
from .services.retrieval_service import RetrievalService
from .storage.metadata_store import MetadataStore


@dataclass
class Container:
    settings: Settings
    store: MetadataStore
    embedder: Embedder
    retrieval: RetrievalService
    documents: DocumentService
    llm: LLMBackend
    rag: RAGService
    experiments: ExperimentService

    def close(self) -> None:
        self.documents.shutdown()
        self.store.close()


def build_container(
    settings: Settings,
    embedder: Optional[Embedder] = None,
    llm: Optional[LLMBackend] = None,
) -> Container:
    settings.ensure_dirs()
    store = MetadataStore(settings.db_path)
    embedder = embedder or SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_batch_size)
    retrieval = RetrievalService(settings.documents_dir, embedder)
    documents = DocumentService(settings, store, embedder, retrieval)
    llm = llm or create_llm_backend(settings)
    rag = RAGService(settings, store, retrieval, llm)
    experiments = ExperimentService(settings, store, rag)
    return Container(settings, store, embedder, retrieval, documents, llm, rag, experiments)
