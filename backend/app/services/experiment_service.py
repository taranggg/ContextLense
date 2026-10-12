"""
Research mode: run one question at several retrieval depths with the same engine.

Only K changes between conditions. Model, prompt, generation parameters,
embedding model, chunks and index are identical, and the settings snapshot is
stored with every comparison. Ad-hoc questions have no ground truth, so answer
correctness is reported as "not evaluated".
"""
from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from typing import Iterator, Optional

from ..config import Settings
from ..schemas import (
    Comparison,
    ComparisonSummary,
    CompareRequest,
    ConditionResult,
    ExperimentSettings,
    GenerationStats,
    Latency,
)
from ..storage.metadata_store import MetadataStore, now_iso
from .evaluation_service import condition_metrics
from .llm_service import GenerationError
from .prompts import PROMPT_VERSION
from .rag_service import RAGService

logger = logging.getLogger("contextlens.research")


class ExperimentService:
    def __init__(self, settings: Settings, store: MetadataStore, rag: RAGService):
        self.settings = settings
        self.store = store
        self.rag = rag

    def experiment_settings(self) -> ExperimentSettings:
        return ExperimentSettings(
            model=self.rag.model_info(),
            embedding_model=self.rag.retrieval.embedder.model_name,
            chunk_size_words=self.settings.chunk_size_words,
            chunk_overlap_words=self.settings.chunk_overlap_words,
            prompt_version=PROMPT_VERSION,
        )

    def _k_values(self, requested: Optional[list[int]]) -> list[int]:
        values = sorted(set(requested or self.settings.research_k_values))
        for k in values:
            self.rag.resolve_k(k)
        return values

    def run_comparison(self, req: CompareRequest) -> Iterator[tuple[str, dict]]:
        """Yields ("start", ...), one ("condition", ...) per condition, then ("done", comparison)."""
        names = self.rag.check_documents(req.document_ids)
        k_values = self._k_values(req.k_values)
        labels = (["no_rag"] if req.include_no_rag else []) + [f"k={k}" for k in k_values]
        yield "start", {"conditions": labels, "settings": self.experiment_settings().model_dump()}

        results: list[ConditionResult] = []
        if req.include_no_rag:
            result = self._run_no_rag(req.question)
            results.append(result)
            yield "condition", result.model_dump()

        for k in k_values:
            result = self._run_k(req.question, req.document_ids, k)
            results.append(result)
            yield "condition", result.model_dump()

        comparison = Comparison(
            id=secrets.token_hex(8),
            created_at=now_iso(),
            question=req.question,
            document_ids=list(dict.fromkeys(req.document_ids)),
            document_names=names,
            settings=self.experiment_settings(),
            conditions=results,
        )
        self.store.save_comparison(
            comparison.id, comparison.created_at, comparison.question, comparison.document_ids, comparison.model_dump()
        )
        yield "done", comparison.model_dump()

    def compare(self, req: CompareRequest) -> Comparison:
        final = None
        for event, payload in self.run_comparison(req):
            if event == "done":
                final = payload
        assert final is not None
        return Comparison.model_validate(final)

    def _run_k(self, question: str, document_ids: list[str], k: int) -> ConditionResult:
        retrieval = self.rag.retrieve(question, document_ids, k)
        try:
            resp = self.rag.answer_from_sources(question, retrieval.chunks, k, retrieval.retrieval_ms)
        except GenerationError as exc:
            return ConditionResult(condition=f"k={k}", k=k, retrieved=retrieval.chunks, error=str(exc))
        included = retrieval.chunks[: resp.generation.sources_in_prompt]
        evidence = "\n".join(c.text for c in included)
        return ConditionResult(
            condition=f"k={k}",
            k=k,
            answer=resp.answer,
            citations=resp.citations,
            invalid_citations=resp.invalid_citations,
            retrieved=resp.retrieved,
            latency=resp.latency,
            generation=resp.generation,
            metrics=condition_metrics(resp.answer, evidence, {c.source_label for c in included}),
        )

    def _run_no_rag(self, question: str) -> ConditionResult:
        try:
            gen = self.rag.answer_without_context(question)
        except GenerationError as exc:
            return ConditionResult(condition="no_rag", k=None, error=str(exc))
        return ConditionResult(
            condition="no_rag",
            k=None,
            answer=gen.text,
            latency=Latency(retrieval_ms=0.0, generation_ms=round(gen.generation_ms, 2), total_ms=round(gen.generation_ms, 2)),
            generation=GenerationStats(
                prompt_tokens=gen.prompt_tokens, completion_tokens=gen.completion_tokens, finish_reason=gen.finish_reason
            ),
            metrics=condition_metrics(gen.text, "", None),
        )

    # ------------------------------------------------------------------ persisted results

    def list_comparisons(self) -> list[ComparisonSummary]:
        return [
            ComparisonSummary(
                id=c["id"],
                created_at=c["created_at"],
                question=c["question"],
                document_names=c.get("document_names", []),
                conditions=[cond["condition"] for cond in c.get("conditions", [])],
            )
            for c in self.store.list_comparisons()
        ]

    def get_comparison(self, comparison_id: str) -> Optional[Comparison]:
        data = self.store.get_comparison(comparison_id)
        return Comparison.model_validate(data) if data else None

    def benchmark_dir(self) -> Path:
        return self.settings.results_dir / "benchmark"

    def list_benchmark_runs(self) -> list[dict]:
        root = self.benchmark_dir()
        runs = []
        if root.exists():
            for summary_path in root.glob("*/summary.json"):
                try:
                    runs.append(json.loads(summary_path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    logger.warning("Skipping unreadable benchmark summary %s", summary_path.parent.name)
        return sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)

    def get_benchmark_run(self, run_id: str) -> Optional[dict]:
        if not run_id.replace("-", "").replace("_", "").isalnum():
            return None
        run_dir = self.benchmark_dir() / run_id
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            return None
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        records = []
        runs_path = run_dir / "runs.jsonl"
        if runs_path.exists():
            with open(runs_path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
        return {"summary": summary, "runs": records}
