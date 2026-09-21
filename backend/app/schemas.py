from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class RetrievedChunk(BaseModel):
    rank: int
    chunk_id: str
    document: str
    page: int
    text: str
    word_count: Optional[int] = 0
    similarity: float
    retrieval_time_ms: Optional[float] = 0

class QueryRequest(BaseModel):
    question: str
    k: int = 5

class Metrics(BaseModel):
    context_relevance: float = 0.0
    answer_accuracy: Optional[float] = None
    hallucination_rate: Optional[float] = None
    response_time_ms: float = 0
    retrieval_time_ms: float = 0
    generation_time_ms: float = 0

class QueryResponse(BaseModel):
    question: str
    k: int
    answer: str
    sources: List[Dict[str, Any]] = []
    retrieved_chunks: List[RetrievedChunk] = []
    metrics: Metrics
    generation_meta: Optional[Dict[str, Any]] = None

class ExperimentRequest(BaseModel):
    question: str

class ExperimentKResult(BaseModel):
    k: int
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    metrics: Metrics
    sources: List[Dict[str, Any]] = []

class ExperimentResponse(BaseModel):
    question: str
    results: List[ExperimentKResult]

class HealthResponse(BaseModel):
    status: str
    embedding_model: Optional[str] = None
    faiss_index_size: Optional[int] = None
    llm_provider: Optional[str] = None
    benchmark_loaded: bool = False

class ResultsSummary(BaseModel):
    total_runs: int
    k_values: List[int]
    aggregated: List[Dict[str, Any]] = []
    figures: List[str] = []

class QuestionResult(BaseModel):
    question_id: str
    question: str
    results: List[Dict[str, Any]] = []
