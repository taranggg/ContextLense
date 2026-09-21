import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import get_retriever
from src.generator import get_llm_provider
from src.evaluation import evaluate_relevance, evaluate_hallucination
from src.config import BENCHMARK_PATH
from src.utils import load_json
import time
from typing import List, Dict

class RAGService:
    def __init__(self):
        self.retriever = None
        self.llm = None
        self._init()

    def _init(self):
        try:
            self.retriever = get_retriever()
            self.llm = get_llm_provider()
        except Exception as e:
            print(f"Failed to init RAG service: {e}")
            # Will retry on request

    def ensure_initialized(self):
        if self.retriever is None:
            self.retriever = get_retriever()
        if self.llm is None:
            self.llm = get_llm_provider()

    def query(self, question: str, k: int = 5) -> Dict:
        self.ensure_initialized()
        # Retrieval
        ret_start = time.perf_counter()
        chunks = self.retriever.retrieve(question, k=k)
        retrieval_time = (time.perf_counter() - ret_start) * 1000

        # Generation
        answer, gen_time, gen_meta = self.llm.generate(question, chunks)
        total_time = retrieval_time + gen_time

        # Metrics (relevance, hallucination)
        rel = evaluate_relevance(question, chunks)
        hall = evaluate_hallucination(answer, chunks)

        sources = [{"document": c["document"], "page": c["page"], "chunk_id": c["chunk_id"]} for c in chunks]

        return {
            "question": question,
            "k": k,
            "answer": answer,
            "sources": sources,
            "retrieved_chunks": chunks,
            "metrics": {
                "context_relevance": rel.get("context_relevance",0),
                "hallucination_rate": hall.get("hallucination_rate",0),
                "response_time_ms": total_time,
                "retrieval_time_ms": retrieval_time,
                "generation_time_ms": gen_time,
            },
            "generation_meta": gen_meta,
            "evaluation_raw": {
                "relevance": rel,
                "hallucination": hall,
            }
        }

    def experiment(self, question: str, k_values: List[int] = [1,3,5,10]) -> Dict:
        results = []
        for k in k_values:
            res = self.query(question, k=k)
            results.append({
                "k": k,
                "answer": res["answer"],
                "retrieved_chunks": res["retrieved_chunks"],
                "metrics": res["metrics"],
                "sources": res["sources"],
            })
        return {
            "question": question,
            "results": results
        }

# Singleton
_service_instance = None

def get_rag_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = RAGService()
    return _service_instance
