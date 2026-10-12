"""
Local sentence embeddings.

Vectors are L2-normalised, so the inner product used by the FAISS index equals
cosine similarity (range -1..1).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Protocol

import numpy as np

logger = logging.getLogger("contextlens.embedding")


class EmbeddingUnavailableError(RuntimeError):
    pass


class Embedder(Protocol):
    model_name: str

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return float32 array of shape (len(texts), dim), L2-normalised."""
        ...

    def status(self) -> tuple[str, Optional[str]]:
        ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()
        self._error: Optional[str] = None
        self.load_time_s: Optional[float] = None

    def _ensure_loaded(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    start = time.perf_counter()
                    try:  # prefer the local cache; only reach the network if the model was never downloaded
                        self._model = SentenceTransformer(self.model_name, local_files_only=True)
                    except Exception:
                        self._model = SentenceTransformer(self.model_name)
                    self.load_time_s = time.perf_counter() - start
                    self._error = None
                    logger.info("Loaded embedding model %s in %.1fs", self.model_name, self.load_time_s)
                except Exception as exc:
                    self._error = f"Could not load embedding model '{self.model_name}': {exc}"
                    logger.error(self._error)
                    raise EmbeddingUnavailableError(self._error) from exc
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self._ensure_loaded()
        if not texts:
            return np.zeros((0, model.get_sentence_embedding_dimension()), dtype=np.float32)
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vectors, dtype=np.float32)

    def warm_up(self) -> None:
        try:
            self._ensure_loaded()
        except EmbeddingUnavailableError:
            pass

    def status(self) -> tuple[str, Optional[str]]:
        if self._model is not None:
            return "ready", f"{self.model_name} (cosine similarity)"
        if self._error:
            return "error", self._error
        return ("loading", self.model_name) if self._lock.locked() else ("not_loaded", f"{self.model_name} loads on first use")
