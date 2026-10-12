"""Pydantic models shared by services and the HTTP API."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- documents


class DocumentStatus(str, Enum):
    queued = "queued"
    extracting = "extracting"
    chunking = "chunking"
    embedding = "embedding"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"


class PageRecord(BaseModel):
    document_id: str
    document_name: str
    page: int  # 1-based, matches the PDF's physical page order
    text: str
    paragraphs: list[str] = []
    word_count: int
    has_text: bool


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    index: int
    pages: list[int]
    text: str
    word_count: int
    page_starts: list[tuple[int, int]] = Field(default=[], description="(character offset, page) where each page's text begins in `text`.")


class DocumentInfo(BaseModel):
    id: str
    filename: str
    status: DocumentStatus
    is_sample: bool = False
    size_bytes: int
    page_count: Optional[int] = None
    pages_with_text: Optional[int] = None
    chunk_count: Optional[int] = None
    word_count: Optional[int] = None
    embedding_model: Optional[str] = None
    chunk_size_words: Optional[int] = None
    chunk_overlap_words: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: list[str] = []
    created_at: str
    updated_at: str


class DocumentList(BaseModel):
    documents: list[DocumentInfo]


class UploadError(BaseModel):
    filename: str
    code: str
    message: str


class BatchUploadResult(BaseModel):
    """Per-file outcome of a multi-file upload: accepted files are processing, rejected ones say why."""

    documents: list[DocumentInfo]
    errors: list[UploadError]


class ChunkPage(BaseModel):
    document_id: str
    total: int
    offset: int
    limit: int
    chunks: list[Chunk]


# --------------------------------------------------------------------------- retrieval / RAG


class RetrievedChunk(BaseModel):
    rank: int
    source_label: str  # "S1", "S2", ... — the marker the model is asked to cite
    chunk_id: str
    document_id: str
    document_name: str
    pages: list[int]
    text: str
    word_count: int
    page_starts: list[tuple[int, int]] = []
    similarity: float = Field(description="Cosine similarity between query and chunk embeddings. A retrieval signal, not proof of support.")


class Citation(BaseModel):
    source_label: str
    rank: int
    chunk_id: str
    document_id: str
    document_name: str
    pages: list[int]
    excerpt_pages: list[int] = Field(description="Pages the excerpt itself comes from (subset of `pages`).")
    similarity: float
    excerpt: str


class ModelInfo(BaseModel):
    runtime: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    context_tokens: int


class GenerationStats(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    context_truncated: bool = False
    sources_in_prompt: int = 0


class Latency(BaseModel):
    retrieval_ms: float
    generation_ms: Optional[float] = None
    total_ms: float


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: list[str] = Field(min_length=1)
    k: Optional[int] = Field(default=None, ge=1)

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        return v


class ChatResponse(BaseModel):
    question: str
    answer: str
    abstained: bool
    citations: list[Citation]
    invalid_citations: list[str] = Field(default=[], description="Markers the model produced that do not match any supplied source.")
    retrieved: list[RetrievedChunk]
    k: int
    latency: Latency
    model: ModelInfo
    generation: GenerationStats
    cancelled: bool = False


# --------------------------------------------------------------------------- conversations (chat memory)


class SavedTurn(BaseModel):
    id: str
    question: str
    k: int
    status: Literal["done", "cancelled"]
    response: Optional[ChatResponse] = None
    created_at: str


class Conversation(BaseModel):
    document_ids: list[str]
    document_names: list[str]
    title: str
    turns: list[SavedTurn]
    created_at: str
    updated_at: str


class ConversationSummary(BaseModel):
    document_ids: list[str]
    document_names: list[str]
    title: str
    turn_count: int
    created_at: str
    updated_at: str


class ConversationList(BaseModel):
    conversations: list[ConversationSummary]


# --------------------------------------------------------------------------- health


class ComponentStatus(BaseModel):
    status: Literal["ready", "loading", "not_loaded", "unavailable", "not_downloaded", "not_configured", "error"]
    detail: Optional[str] = None


class LLMStatus(ComponentStatus):
    runtime: str
    model: str
    load_time_s: Optional[float] = None


class ReadinessResponse(BaseModel):
    ready: bool
    backend: ComponentStatus
    storage: ComponentStatus
    embedding: ComponentStatus
    llm: LLMStatus
    documents_ready: int
    limits: dict


# --------------------------------------------------------------------------- research


class ClaimCheck(BaseModel):
    claim: str
    label: Literal["supported", "unsupported"]
    support_ratio: float
    missing_numbers: list[str] = []


class ConditionMetrics(BaseModel):
    """Automatically computed signals. None means not computed."""

    abstained: bool
    citation_count: int
    invalid_citation_count: int
    citation_validity: Optional[float] = None
    claims_total: int = 0
    claims_lexically_supported: int = 0
    claims_lexically_unsupported: int = 0
    claim_checks: list[ClaimCheck] = []
    method: str = "lexical_heuristic"


class ConditionResult(BaseModel):
    condition: str  # "k=1", "k=3", ..., "no_rag"
    k: Optional[int]
    answer: Optional[str] = None
    citations: list[Citation] = []
    invalid_citations: list[str] = []
    retrieved: list[RetrievedChunk] = []
    latency: Optional[Latency] = None
    generation: Optional[GenerationStats] = None
    metrics: Optional[ConditionMetrics] = None
    error: Optional[str] = None


class CompareRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: list[str] = Field(min_length=1)
    k_values: Optional[list[int]] = None
    include_no_rag: bool = False

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        return v


class ExperimentSettings(BaseModel):
    model: ModelInfo
    embedding_model: str
    similarity: str = "cosine (inner product of L2-normalised vectors)"
    chunk_size_words: int
    chunk_overlap_words: int
    prompt_version: str


class Comparison(BaseModel):
    id: str
    created_at: str
    question: str
    document_ids: list[str]
    document_names: list[str]
    settings: ExperimentSettings
    conditions: list[ConditionResult]
    evaluation_status: str = Field(
        default="not_evaluated",
        description="Ad-hoc questions have no ground truth, so correctness is not evaluated.",
    )


class ComparisonSummary(BaseModel):
    id: str
    created_at: str
    question: str
    document_names: list[str]
    conditions: list[str]


class ResearchResults(BaseModel):
    comparisons: list[ComparisonSummary]
    benchmark_runs: list[dict]
