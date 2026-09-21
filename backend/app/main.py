from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.schemas import (
    QueryRequest, QueryResponse, ExperimentRequest, ExperimentResponse,
    HealthResponse, ResultsSummary, RetrievedChunk, Metrics
)
from backend.app.services.rag_service import get_rag_service
from backend.app.services.experiment_service import get_experiment_service
from backend.app.config import RESULTS_DIR
from src.config import FAISS_INDEX_PATH, EMBEDDING_MODEL, get_llm_config, BENCHMARK_PATH
from src.utils import load_json

app = FastAPI(
    title="ContextLens API",
    description="Investigating impact of retrieval depth on RAG answer quality",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount figures static if exists
figures_dir = RESULTS_DIR / "figures"
if figures_dir.exists():
    app.mount("/figures", StaticFiles(directory=str(figures_dir)), name="figures")

@app.get("/health", response_model=HealthResponse)
def health():
    try:
        rag = get_rag_service()
        faiss_size = rag.retriever.index.ntotal if rag.retriever and rag.retriever.index else 0
    except Exception as e:
        faiss_size = 0

    llm_cfg = get_llm_config()
    benchmark_loaded = BENCHMARK_PATH.exists()

    return HealthResponse(
        status="ok",
        embedding_model=EMBEDDING_MODEL,
        faiss_index_size=faiss_size,
        llm_provider=llm_cfg.get("provider"),
        benchmark_loaded=benchmark_loaded
    )

@app.post("/api/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if req.k not in [1,3,5,10]:
        # allow but warn
        pass
    try:
        rag = get_rag_service()
        result = rag.query(req.question, k=req.k)

        # Convert retrieved chunks to schema
        chunks = []
        for c in result["retrieved_chunks"]:
            chunks.append(RetrievedChunk(
                rank=c.get("rank",0),
                chunk_id=c.get("chunk_id",""),
                document=c.get("document",""),
                page=c.get("page",0),
                text=c.get("text",""),
                word_count=c.get("word_count",0),
                similarity=c.get("similarity",0),
                retrieval_time_ms=c.get("retrieval_time_ms",0)
            ))

        metrics = Metrics(
            context_relevance=result["metrics"]["context_relevance"],
            hallucination_rate=result["metrics"]["hallucination_rate"],
            response_time_ms=result["metrics"]["response_time_ms"],
            retrieval_time_ms=result["metrics"]["retrieval_time_ms"],
            generation_time_ms=result["metrics"]["generation_time_ms"],
        )

        return QueryResponse(
            question=result["question"],
            k=result["k"],
            answer=result["answer"],
            sources=result["sources"],
            retrieved_chunks=chunks,
            metrics=metrics,
            generation_meta=result.get("generation_meta")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/experiment", response_model=ExperimentResponse)
def experiment_endpoint(req: ExperimentRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        rag = get_rag_service()
        exp_result = rag.experiment(req.question, k_values=[1,3,5,10])

        results = []
        for r in exp_result["results"]:
            chunks = []
            for c in r["retrieved_chunks"]:
                chunks.append(RetrievedChunk(
                    rank=c.get("rank",0),
                    chunk_id=c.get("chunk_id",""),
                    document=c.get("document",""),
                    page=c.get("page",0),
                    text=c.get("text",""),
                    word_count=c.get("word_count",0),
                    similarity=c.get("similarity",0),
                    retrieval_time_ms=c.get("retrieval_time_ms",0)
                ))
            metrics = Metrics(
                context_relevance=r["metrics"]["context_relevance"],
                hallucination_rate=r["metrics"]["hallucination_rate"],
                response_time_ms=r["metrics"]["response_time_ms"],
                retrieval_time_ms=r["metrics"]["retrieval_time_ms"],
                generation_time_ms=r["metrics"]["generation_time_ms"],
            )
            results.append({
                "k": r["k"],
                "answer": r["answer"],
                "retrieved_chunks": chunks,
                "metrics": metrics,
                "sources": r["sources"]
            })

        return ExperimentResponse(
            question=exp_result["question"],
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results/summary")
def results_summary():
    try:
        exp_service = get_experiment_service()
        return exp_service.get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results/question/{question_id}")
def results_by_question(question_id: str):
    try:
        exp_service = get_experiment_service()
        res = exp_service.get_question_result(question_id)
        if not res:
            raise HTTPException(status_code=404, detail="Question ID not found or no results")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/benchmark")
def get_benchmark():
    if not BENCHMARK_PATH.exists():
        raise HTTPException(status_code=404, detail="Benchmark not found")
    try:
        data = load_json(BENCHMARK_PATH)
        questions = data["questions"] if isinstance(data, dict) and "questions" in data else data
        # Return only questions without ground truth? But for research we return all
        return {
            "total": len(questions),
            "questions": [{"question_id": q["question_id"], "question": q["question"], "category": q["category"]} for q in questions]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/failure-cases")
def get_failure_cases():
    failure_path = RESULTS_DIR / "failure_cases.json"
    if not failure_path.exists():
        return {"failure_cases": [], "message": "No failure cases yet. Run experiment first."}
    try:
        data = load_json(failure_path)
        return {"failure_cases": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
