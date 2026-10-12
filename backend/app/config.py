"""
Backend configuration.

Every value can be overridden with an environment variable (or a `.env` file at
the repository root). Server-only settings live here and are never sent to the
frontend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


@dataclass(frozen=True)
class Settings:
    # Server
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    # Storage
    data_dir: Path = PROJECT_ROOT / "data"
    results_dir: Path = PROJECT_ROOT / "results"
    max_upload_mb: int = 25
    max_files_per_upload: int = 5

    # Chunking (identical for every K)
    chunk_size_words: int = 500
    chunk_overlap_words: int = 80
    min_page_words: int = 5  # pages with fewer extracted words are treated as having no text

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32

    # Retrieval
    default_top_k: int = 5
    research_k_values: tuple[int, ...] = (1, 3, 5, 10)
    max_top_k: int = 20

    # Local LLM
    llm_runtime: str = "mlx"  # "mlx" or "none"
    llm_model: str = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    llm_max_tokens: int = 384
    llm_temperature: float = 0.0
    llm_top_p: float = 1.0
    llm_context_tokens: int = 12288
    llm_preload: bool = True
    llm_allow_download: bool = False

    # Request limits
    max_question_chars: int = 2000

    # Derived paths
    documents_dir: Path = field(init=False)
    db_path: Path = field(init=False)
    benchmark_path: Path = field(init=False)
    samples_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "documents_dir", self.data_dir / "documents")
        object.__setattr__(self, "db_path", self.data_dir / "contextlens.db")
        object.__setattr__(self, "benchmark_path", self.data_dir / "benchmark" / "ContextLens_Benchmark_50_Questions.json")
        object.__setattr__(self, "samples_dir", self.data_dir / "raw")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def with_overrides(self, **kwargs) -> "Settings":
        return replace(self, **kwargs)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    origins = tuple(
        o.strip().rstrip("/")
        for o in _env("FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    )
    k_values = tuple(int(k) for k in _env("RESEARCH_K_VALUES", "1,3,5,10").split(",") if k.strip())
    return Settings(
        backend_host=_env("BACKEND_HOST", "127.0.0.1"),
        backend_port=_env_int("BACKEND_PORT", 8000),
        frontend_origins=origins,
        data_dir=_resolve(_env("DATA_DIR", "./data")),
        results_dir=_resolve(_env("RESULTS_DIR", "./results")),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 25),
        max_files_per_upload=_env_int("MAX_FILES_PER_UPLOAD", 5),
        chunk_size_words=_env_int("CHUNK_SIZE_WORDS", 500),
        chunk_overlap_words=_env_int("CHUNK_OVERLAP_WORDS", 80),
        embedding_model=_env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        default_top_k=_env_int("DEFAULT_TOP_K", 5),
        research_k_values=k_values,
        llm_runtime=_env("LLM_RUNTIME", "mlx").lower(),
        llm_model=_env("LLM_MODEL", "mlx-community/Qwen3-4B-Instruct-2507-4bit"),
        llm_max_tokens=_env_int("LLM_MAX_TOKENS", 384),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.0),
        llm_top_p=_env_float("LLM_TOP_P", 1.0),
        llm_context_tokens=_env_int("LLM_CONTEXT_TOKENS", 12288),
        llm_preload=_env_bool("LLM_PRELOAD", True),
        llm_allow_download=_env_bool("LLM_ALLOW_DOWNLOAD", False),
    )
