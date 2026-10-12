"""
Offline benchmark for the research question:
    How does retrieval depth affect the quality of answers from a local LLM using RAG?

Usage (from the repository root):
    python -m backend.app.research.benchmark ingest      # index the sample PDFs in data/raw as sample documents
    python -m backend.app.research.benchmark validate    # check benchmark source pages against extracted text
    python -m backend.app.research.benchmark run [--questions N] [--conditions no_rag,k1,k3,k5,k10,gold] [--run-id ID]
    python -m backend.app.research.benchmark summarize --run-id ID

Conditions share the model checkpoint, generation parameters, RAG prompt,
embedding model, chunks and index; only the evidence supplied changes:
    no_rag   no retrieved context (separate no-context prompt, same model and parameters)
    k1..k10  Top-K retrieved chunks
    gold     the benchmark's cited source page, only for questions whose page
             reference passed automatic validation

All metrics are rule-based lexical heuristics (see evaluation_service). They
have not been calibrated against human judgements; treat them as signals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import Settings, load_settings
from ..container import Container, build_container
from ..schemas import DocumentStatus, PageRecord, RetrievedChunk
from ..services.evaluation_service import check_claims, fact_coverage, score_accuracy
from ..services.llm_service import GenerationError, LLMUnavailableError
from ..services.prompts import PROMPT_VERSION, is_abstention
from ..services.rag_service import parse_citation_labels
from ..storage.document_files import DocumentFiles, read_jsonl

logger = logging.getLogger("contextlens.benchmark")

VALIDATION_SUPPORTED = 0.5  # share of required facts that must appear on the cited page
ALL_CONDITIONS = ["no_rag", "k1", "k3", "k5", "k10", "gold"]


# --------------------------------------------------------------------------- helpers


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_questions(settings: Settings) -> tuple[list[dict], str]:
    raw = settings.benchmark_path.read_bytes()
    data = json.loads(raw)
    questions = data["questions"] if isinstance(data, dict) else data
    return questions, hashlib.sha256(raw).hexdigest()[:16]


def sample_documents(c: Container) -> dict[str, str]:
    """filename -> document id for ready sample documents."""
    return {d.filename: d.id for d in c.store.list_documents() if d.is_sample and d.status == DocumentStatus.ready}


def ingest_samples(c: Container) -> dict[str, str]:
    existing = sample_documents(c)
    for pdf in sorted(c.settings.samples_dir.glob("*.pdf")):
        if pdf.name in existing:
            print(f"  {pdf.name}: already indexed ({existing[pdf.name]})")
            continue
        print(f"  {pdf.name}: indexing ...", flush=True)
        doc = c.documents.ingest_file(pdf, is_sample=True)
        doc = c.documents.get(doc.id)
        print(f"  {pdf.name}: {doc.status.value} ({doc.page_count} pages, {doc.chunk_count} chunks)")
    return sample_documents(c)


def load_pages(c: Container, doc_id: str) -> dict[int, PageRecord]:
    return {p.page: p for p in read_jsonl(DocumentFiles(c.settings.documents_dir, doc_id).pages, PageRecord)}


# --------------------------------------------------------------------------- validation


def validate_benchmark(c: Container, docs: dict[str, str]) -> dict:
    questions, digest = load_questions(c.settings)
    pages_by_doc = {name: load_pages(c, doc_id) for name, doc_id in docs.items()}
    items = []
    for q in questions:
        facts = q.get("required_facts", [])
        name, cited = q.get("source_document"), q.get("source_page")
        pages = pages_by_doc.get(name)
        item = {"question_id": q["question_id"], "source_document": name, "source_page": cited}
        if pages is None:
            item.update(status="document_missing", cited_page_coverage=None, best_pages=[])
            items.append(item)
            continue
        coverage = {}
        for number, page in pages.items():
            covered, _ = fact_coverage(facts, page.text)
            coverage[number] = len(covered) / len(facts) if facts else 0.0
        cited_cov = coverage.get(cited, 0.0)
        best = max(coverage.values(), default=0.0)
        best_pages = sorted(p for p, v in coverage.items() if v == best and best > 0)
        covered, missing = fact_coverage(facts, pages[cited].text) if cited in pages else ([], facts)
        if cited_cov >= VALIDATION_SUPPORTED:
            status = "supported_on_cited_page"
        elif best >= VALIDATION_SUPPORTED:
            status = "found_on_other_page"
        else:
            status = "not_found_in_document"
        item.update(
            status=status,
            cited_page_coverage=round(cited_cov, 3),
            best_page_coverage=round(best, 3),
            best_pages=best_pages[:5],
            facts_found_on_cited_page=covered,
            facts_missing_on_cited_page=missing,
        )
        items.append(item)

    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    report = {
        "generated_at": now_iso(),
        "benchmark_sha256_16": digest,
        "method": (
            "Automatic lexical check: a required fact counts as present on a page when >= 60% of its content terms "
            "and all of its numbers appear in the page text extracted by PyMuPDF. A question's page reference is "
            f"'supported_on_cited_page' when >= {int(VALIDATION_SUPPORTED * 100)}% of its required facts are present "
            "on the cited page. This is not human verification; the benchmark file itself is never modified."
        ),
        "counts": counts,
        "questions": items,
    }
    out = c.settings.benchmark_path.parent / "validation_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


# --------------------------------------------------------------------------- one run


def _retrieved_summary(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "rank": ch.rank,
            "source_label": ch.source_label,
            "chunk_id": ch.chunk_id,
            "document_name": ch.document_name,
            "pages": ch.pages,
            "similarity": ch.similarity,
            "text": ch.text,
        }
        for ch in chunks
    ]


def _context_metrics(facts: list[str], chunks: list[dict], gold: Optional[dict]) -> dict:
    if not chunks:
        return {"fact_recall": None, "fact_bearing_chunk_precision": None, "gold_page_retrieved": None}
    joined = "\n".join(ch["text"] for ch in chunks)
    covered, _ = fact_coverage(facts, joined)
    bearing = sum(1 for ch in chunks if fact_coverage(facts, ch["text"])[0])
    gold_hit = None
    if gold:
        gold_hit = any(ch["document_name"] == gold["document"] and gold["page"] in ch["pages"] for ch in chunks)
    return {
        "fact_recall": round(len(covered) / len(facts), 4) if facts else None,
        "fact_bearing_chunk_precision": round(bearing / len(chunks), 4),
        "gold_page_retrieved": gold_hit,
    }


def compute_metrics(record: dict) -> dict:
    """Rule-based metrics from a stored record (answer + supplied context). Used by `run` and `rescore`."""
    answer, facts, gold, condition = record["answer"], record["required_facts"], record.get("gold"), record["condition"]
    included = record["retrieved"][: (record.get("generation") or {}).get("sources_in_prompt", 0)]
    evidence = "\n".join(ch["text"] for ch in included)
    claims = check_claims(answer, evidence) if evidence else []
    labels = parse_citation_labels(answer)
    invalid = record.get("invalid_citations", [])
    cites_gold = None
    if gold and condition != "no_rag":
        cites_gold = any(
            ci["document_name"] == gold["document"] and gold["page"] in ci["pages"] for ci in record.get("citations", [])
        )
    retrieval_based = condition != "no_rag"
    return {
        "accuracy": score_accuracy(facts, answer),
        "context": _context_metrics(facts, included, gold),
        "claims": {
            "method": "lexical_heuristic",
            "total": len(claims),
            "supported": sum(1 for x in claims if x.label == "supported"),
            "unsupported": sum(1 for x in claims if x.label == "unsupported"),
            "contradicted": None,  # not detectable with lexical checks
            "checks": [x.model_dump() for x in claims],
        } if retrieval_based else None,
        "citations": {
            "count": len(labels),
            "invalid": len(invalid),
            "validity": round((len(labels) - len(invalid)) / len(labels), 4) if labels else None,
            "cites_gold_page": cites_gold,
        } if retrieval_based else None,
    }


def run_condition(c: Container, q: dict, condition: str, docs: dict[str, str], gold: Optional[dict]) -> dict:
    question = q["question"]
    facts = q.get("required_facts", [])
    record = {
        "question_id": q["question_id"],
        "category": q.get("category"),
        "condition": condition,
        "k": int(condition[1:]) if condition.startswith("k") else None,
        "question": question,
        "ground_truth": q.get("ground_truth"),
        "required_facts": facts,
        "gold": gold,
        "created_at": now_iso(),
    }
    try:
        if condition == "no_rag":
            gen = c.rag.answer_without_context(question)
            answer, chunks = gen.text, []
            latency = {"retrieval_ms": 0.0, "generation_ms": round(gen.generation_ms, 2), "total_ms": round(gen.generation_ms, 2)}
            generation = {"prompt_tokens": gen.prompt_tokens, "completion_tokens": gen.completion_tokens,
                          "finish_reason": gen.finish_reason, "context_truncated": False, "sources_in_prompt": 0}
            citations, invalid = [], []
        else:
            if condition == "gold":
                page = load_pages(c, docs[gold["document"]])[gold["page"]]
                chunks = [RetrievedChunk(
                    rank=1, source_label="S1", chunk_id=f"gold-{q['question_id']}", document_id=docs[gold["document"]],
                    document_name=gold["document"], pages=[gold["page"]], text=page.text,
                    word_count=page.word_count, similarity=1.0,
                )]
                resp = c.rag.answer_from_sources(question, chunks, 1, 0.0)
            else:
                k = record["k"]
                retrieval = c.rag.retrieve(question, list(docs.values()), k)
                chunks = retrieval.chunks
                resp = c.rag.answer_from_sources(question, chunks, k, retrieval.retrieval_ms)
            answer = resp.answer
            latency = resp.latency.model_dump()
            generation = resp.generation.model_dump()
            citations = [{"source_label": ci.source_label, "document_name": ci.document_name, "pages": ci.pages,
                          "excerpt_pages": ci.excerpt_pages} for ci in resp.citations]
            invalid = resp.invalid_citations
    except GenerationError as exc:
        record["error"] = str(exc)
        return record

    record.update(
        answer=answer,
        abstained=is_abstention(answer),
        retrieved=_retrieved_summary(chunks),
        citations=citations,
        invalid_citations=invalid,
        latency=latency,
        generation=generation,
    )
    record["metrics"] = compute_metrics(record)
    return record


# --------------------------------------------------------------------------- summary & statistics


def _mean(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 4) if vals else None


def _median(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 2) if vals else None


def _rate(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(sum(1 for v in vals if v) / len(vals), 4) if vals else None


def aggregate(records: list[dict]) -> dict:
    ok = [r for r in records if "error" not in r]
    m = lambda path: [_dig(r, path) for r in ok]  # noqa: E731
    claims_total = sum(_dig(r, "metrics.claims.total") or 0 for r in ok)
    claims_sup = sum(_dig(r, "metrics.claims.supported") or 0 for r in ok)
    scores = [_dig(r, "metrics.accuracy.score") for r in ok]
    return {
        "n": len(records),
        "errors": len(records) - len(ok),
        "accuracy_normalised_mean": _mean([s / 2 for s in scores if s is not None]),
        "accuracy_score_counts": {str(v): scores.count(v) for v in (0, 1, 2)},
        "abstention_rate": _rate(m("abstained")),
        "context_fact_recall_mean": _mean(m("metrics.context.fact_recall")),
        "context_fact_bearing_precision_mean": _mean(m("metrics.context.fact_bearing_chunk_precision")),
        "gold_page_retrieved_rate": _rate(m("metrics.context.gold_page_retrieved")),
        "claims_total": claims_total,
        "claims_lexically_supported_rate": round(claims_sup / claims_total, 4) if claims_total else None,
        "citation_validity_mean": _mean(m("metrics.citations.validity")),
        "cites_gold_page_rate": _rate(m("metrics.citations.cites_gold_page")),
        "retrieval_ms_median": _median(m("latency.retrieval_ms")),
        "generation_ms_median": _median(m("latency.generation_ms")),
        "total_ms_median": _median(m("latency.total_ms")),
        "total_ms_mean": _mean(m("latency.total_ms")),
        "prompt_tokens_mean": _mean(m("generation.prompt_tokens")),
        "context_truncated_count": sum(1 for v in m("generation.context_truncated") if v),
    }


def _dig(obj, path: str):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _holm(pvalues: list[Optional[float]]) -> list[Optional[float]]:
    indexed = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    m = len(indexed)
    adjusted: list[Optional[float]] = [None] * len(pvalues)
    running = 0.0
    for rank, (p, i) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = round(running, 6)
    return adjusted


def paired_tests(records: list[dict], conditions: list[str]) -> list[dict]:
    """Wilcoxon signed-rank on per-question values for each pair of conditions, Holm-corrected per metric."""
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        return []
    metrics = {"accuracy_score": "metrics.accuracy.score", "total_ms": "latency.total_ms"}
    by_key = {(r["question_id"], r["condition"]): r for r in records if "error" not in r}
    rows = []
    for metric, path in metrics.items():
        block = []
        for i, a in enumerate(conditions):
            for b in conditions[i + 1 :]:
                pairs = [
                    (_dig(by_key[(qid, a)], path), _dig(by_key[(qid, b)], path))
                    for (qid, cond) in by_key
                    if cond == a and (qid, b) in by_key
                ]
                pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
                row = {"metric": metric, "a": a, "b": b, "n": len(pairs), "mean_a": None, "mean_b": None,
                       "mean_diff_b_minus_a": None, "p_value": None, "note": None}
                if pairs:
                    row["mean_a"] = round(statistics.fmean(x for x, _ in pairs), 4)
                    row["mean_b"] = round(statistics.fmean(y for _, y in pairs), 4)
                    row["mean_diff_b_minus_a"] = round(row["mean_b"] - row["mean_a"], 4)
                if len(pairs) < 6:
                    row["note"] = "too few paired questions for a test"
                elif all(x == y for x, y in pairs):
                    row["note"] = "identical on every question"
                else:
                    try:
                        row["p_value"] = round(float(wilcoxon([x for x, _ in pairs], [y for _, y in pairs]).pvalue), 6)
                    except ValueError as exc:
                        row["note"] = str(exc)
                block.append(row)
        for row, adj in zip(block, _holm([r["p_value"] for r in block])):
            row["p_holm"] = adj
        rows.extend(block)
    return rows


def summarize(c: Container, run_dir: Path) -> dict:
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    with open(run_dir / "runs.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                latest[(r["question_id"], r["condition"])] = r  # a resumed run may retry a failed pair
    records = list(latest.values())
    conditions = [x for x in config["conditions"] if any(r["condition"] == x for r in records)]
    validated_ids = {r["question_id"] for r in records if r.get("gold")}
    summary = {
        **config,
        "status": "complete" if len(records) >= config["planned_runs"] else "partial",
        "completed_runs": len(records),
        "finished_at": now_iso(),
        "by_condition": {x: aggregate([r for r in records if r["condition"] == x]) for x in conditions},
        "by_condition_validated_subset": {
            x: aggregate([r for r in records if r["condition"] == x and r["question_id"] in validated_ids])
            for x in conditions
        },
        "validated_question_count": len(validated_ids),
        "paired_tests": paired_tests(records, conditions),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- run


def run_benchmark(c: Container, conditions: list[str], limit: Optional[int], run_id: Optional[str]) -> Path:
    docs = sample_documents(c)
    if not docs:
        raise SystemExit("No sample documents are indexed. Run: python -m backend.app.research.benchmark ingest")
    questions, digest = load_questions(c.settings)
    if limit:
        questions = questions[:limit]
    report = validate_benchmark(c, docs)
    validation = {it["question_id"]: it for it in report["questions"]}

    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = c.settings.results_dir / "benchmark" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    gold_eligible = sum(1 for q in questions if validation[q["question_id"]]["status"] == "supported_on_cited_page")
    planned = sum(1 for x in conditions if x != "gold") * len(questions) + (gold_eligible if "gold" in conditions else 0)
    config = {
        "run_id": run_id,
        "started_at": now_iso(),
        "benchmark_file": c.settings.benchmark_path.name,
        "benchmark_sha256_16": digest,
        "benchmark_note": "Questions were generated from the sample PDFs (see benchmark metadata), not written by domain experts.",
        "question_count": len(questions),
        "conditions": conditions,
        "planned_runs": planned,
        "documents": [{"id": doc_id, "filename": name} for name, doc_id in sorted(docs.items())],
        "model": c.rag.model_info().model_dump(),
        "embedding_model": c.embedder.model_name,
        "similarity": "cosine",
        "chunk_size_words": c.settings.chunk_size_words,
        "chunk_overlap_words": c.settings.chunk_overlap_words,
        "prompt_version": PROMPT_VERSION,
        "validation_counts": report["counts"],
        "evaluation": {
            "method": "rule-based lexical heuristics",
            "accuracy": "0/1/2 from required-fact coverage (>=80% -> 2, >=40% -> 1); abstentions score 0; normalised as score/2",
            "context_fact_recall": "share of required facts present in the supplied context",
            "context_fact_bearing_precision": "share of supplied chunks containing at least one required fact",
            "gold_page_retrieved": "a supplied chunk includes the validated gold page",
            "claims": "answer sentences labelled supported when >=60% of content terms and all numbers occur in the context; "
                      "'unsupported' means not established by the context, not false; contradictions are not detected",
            "citation_validity": "share of [S#] markers that refer to a supplied source",
            "limitations": "Heuristics have not been validated against human judgements. No LLM judge is used.",
        },
    }
    config_path = run_dir / "config.json"
    if config_path.exists():
        previous = json.loads(config_path.read_text(encoding="utf-8"))
        keys = ("benchmark_sha256_16", "model", "embedding_model", "chunk_size_words", "chunk_overlap_words", "prompt_version")
        if any(previous.get(k) != config[k] for k in keys):
            raise SystemExit(f"Run '{run_id}' exists with different settings; use a new --run-id.")
        config["started_at"] = previous["started_at"]
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    runs_path = run_dir / "runs.jsonl"
    done = set()
    if runs_path.exists():
        with open(runs_path, encoding="utf-8") as f:
            done = {(r["question_id"], r["condition"]) for r in map(json.loads, filter(str.strip, f)) if "error" not in r}

    total, finished, started = planned, len(done), time.time()
    print(f"Run {run_id}: {len(questions)} questions x {conditions} -> {planned} runs ({finished} already done)")
    with open(runs_path, "a", encoding="utf-8") as out:
        for q in questions:
            v = validation[q["question_id"]]
            gold = (
                {"document": q["source_document"], "page": q["source_page"], "validation": v["status"]}
                if v["status"] == "supported_on_cited_page"
                else None
            )
            for condition in conditions:
                if condition == "gold" and gold is None:
                    continue
                if (q["question_id"], condition) in done:
                    continue
                record = run_condition(c, q, condition, docs, gold)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                finished += 1
                rate = (time.time() - started) / max(1, finished - len(done))
                status = "error" if "error" in record else f"score={record['metrics']['accuracy']['score']}"
                print(f"  [{finished}/{total}] {q['question_id']} {condition:7s} {status}  (~{(total - finished) * rate / 60:.0f} min left)", flush=True)
    summary = summarize(c, run_dir)
    print(f"Summary written to {run_dir / 'summary.json'} ({summary['status']})")
    return run_dir


def rescore(c: Container, run_dir: Path) -> dict:
    """Recompute metrics for stored answers (no generation), e.g. after an evaluation fix."""
    runs_path = run_dir / "runs.jsonl"
    with open(runs_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    for r in records:
        if "error" not in r:
            r["abstained"] = is_abstention(r["answer"])
            r["metrics"] = compute_metrics(r)
    tmp = runs_path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(runs_path)
    return summarize(c, run_dir)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.research.benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="index the sample PDFs in data/raw")
    sub.add_parser("validate", help="validate benchmark page references")
    run = sub.add_parser("run", help="run the benchmark")
    run.add_argument("--questions", type=int, default=None, help="limit to the first N questions")
    run.add_argument("--conditions", default=",".join(ALL_CONDITIONS))
    run.add_argument("--run-id", default=None, help="resume or name a run")
    summ = sub.add_parser("summarize", help="recompute summary.json for a run")
    summ.add_argument("--run-id", required=True)
    resc = sub.add_parser("rescore", help="recompute metrics from stored answers, then summarize")
    resc.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    settings = load_settings()
    c = build_container(settings)
    try:
        if args.command == "ingest":
            ingest_samples(c)
        elif args.command == "validate":
            docs = sample_documents(c)
            if not docs:
                raise SystemExit("No sample documents are indexed. Run the 'ingest' command first.")
            report = validate_benchmark(c, docs)
            print(json.dumps(report["counts"], indent=2))
            print(f"Report: {settings.benchmark_path.parent / 'validation_report.json'}")
        elif args.command == "run":
            conditions = [x.strip() for x in args.conditions.split(",") if x.strip()]
            unknown = set(conditions) - set(ALL_CONDITIONS)
            if unknown:
                raise SystemExit(f"Unknown conditions: {sorted(unknown)}")
            try:
                run_benchmark(c, conditions, args.questions, args.run_id)
            except LLMUnavailableError as exc:
                raise SystemExit(f"Local model unavailable: {exc.message}")
        elif args.command == "rescore":
            summary = rescore(c, settings.results_dir / "benchmark" / args.run_id)
            print(json.dumps(summary["by_condition"], indent=2))
        elif args.command == "summarize":
            summary = summarize(c, settings.results_dir / "benchmark" / args.run_id)
            print(json.dumps(summary["by_condition"], indent=2))
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
