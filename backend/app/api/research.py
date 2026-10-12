from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..schemas import Comparison, CompareRequest, ResearchResults
from .deps import container_of
from .errors import APIError
from .sse import sse_response

router = APIRouter(prefix="/api/research", tags=["research"])


def _validate(request: Request, body: CompareRequest) -> None:
    c = container_of(request)
    if len(body.question) > c.settings.max_question_chars:
        raise APIError(422, "question_too_long", f"Questions are limited to {c.settings.max_question_chars} characters.")
    c.rag.check_documents(body.document_ids)
    for k in body.k_values or []:
        c.rag.resolve_k(k)


@router.post("/compare", response_model=Comparison)
def compare(body: CompareRequest, request: Request) -> Comparison:
    """Run one question at K = 1, 3, 5, 10 (by default) with identical settings. Persisted."""
    _validate(request, body)
    return container_of(request).experiments.compare(body)


@router.post("/compare/stream")
def compare_stream(body: CompareRequest, request: Request) -> StreamingResponse:
    """Streamed variant: `start` -> `condition` per finished condition -> `done` | `error`."""
    _validate(request, body)
    experiments = container_of(request).experiments

    def work(emit, should_stop):
        for event, payload in experiments.run_comparison(body):
            if should_stop():
                return
            emit(event, payload)

    return sse_response(work)


@router.get("/results", response_model=ResearchResults)
def results(request: Request) -> ResearchResults:
    """Persisted ad-hoc comparisons and offline benchmark runs. Empty lists mean nothing has been run."""
    experiments = container_of(request).experiments
    return ResearchResults(
        comparisons=experiments.list_comparisons(),
        benchmark_runs=experiments.list_benchmark_runs(),
    )


@router.get("/comparisons/{comparison_id}", response_model=Comparison)
def get_comparison(comparison_id: str, request: Request) -> Comparison:
    comparison = container_of(request).experiments.get_comparison(comparison_id)
    if comparison is None:
        raise APIError(404, "comparison_not_found", "Comparison not found.")
    return comparison


@router.get("/benchmark/{run_id}")
def get_benchmark_run(run_id: str, request: Request) -> dict:
    run = container_of(request).experiments.get_benchmark_run(run_id)
    if run is None:
        raise APIError(404, "benchmark_run_not_found", "Benchmark run not found.")
    return run
