"""
One-off export: turn the raw benchmark run (runs.jsonl + summary.json) into the
flat results.csv / comparison_table.csv / figures/ expected by the assignment
submission structure.

Usage (from the repository root):
    .venv/bin/python scripts/export_results.py --run-id full-50q-2026-10-12
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

CONDITION_ORDER = ["no_rag", "k1", "k3", "k5", "k10", "gold"]
CONDITION_LABEL = {
    "no_rag": "No retrieval",
    "k1": "Top-1",
    "k3": "Top-3",
    "k5": "Top-5",
    "k10": "Top-10",
    "gold": "Gold page (oracle)",
}


def dig(obj: dict, path: str):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def load_records(run_dir: Path) -> list[dict]:
    latest: dict[tuple[str, str], dict] = {}
    with open(run_dir / "runs.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                latest[(r["question_id"], r["condition"])] = r
    return list(latest.values())


def write_results_csv(records: list[dict], out_path: Path) -> None:
    fields = [
        "question_id", "category", "condition", "k",
        "accuracy_score", "accuracy_normalised", "abstained",
        "context_fact_recall", "context_fact_bearing_precision", "gold_page_retrieved",
        "claims_total", "claims_supported", "claims_unsupported",
        "citation_validity", "cites_gold_page",
        "retrieval_ms", "generation_ms", "total_ms",
    ]
    rows = []
    for r in records:
        if "error" in r:
            continue
        score = dig(r, "metrics.accuracy.score")
        rows.append({
            "question_id": r["question_id"],
            "category": r["category"],
            "condition": r["condition"],
            "k": r.get("k"),
            "accuracy_score": score,
            "accuracy_normalised": round(score / 2, 4) if score is not None else None,
            "abstained": r.get("abstained"),
            "context_fact_recall": dig(r, "metrics.context.fact_recall"),
            "context_fact_bearing_precision": dig(r, "metrics.context.fact_bearing_chunk_precision"),
            "gold_page_retrieved": dig(r, "metrics.context.gold_page_retrieved"),
            "claims_total": dig(r, "metrics.claims.total"),
            "claims_supported": dig(r, "metrics.claims.supported"),
            "claims_unsupported": dig(r, "metrics.claims.unsupported"),
            "citation_validity": dig(r, "metrics.citations.validity"),
            "cites_gold_page": dig(r, "metrics.citations.cites_gold_page"),
            "retrieval_ms": dig(r, "latency.retrieval_ms"),
            "generation_ms": dig(r, "latency.generation_ms"),
            "total_ms": dig(r, "latency.total_ms"),
        })
    rows.sort(key=lambda row: (row["question_id"], CONDITION_ORDER.index(row["condition"])))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path} ({len(rows)} rows)")


def write_comparison_table(summary: dict, out_path: Path) -> None:
    fields = [
        "condition", "label", "k", "n",
        "accuracy_normalised_mean", "abstention_rate",
        "context_fact_recall_mean", "context_fact_bearing_precision_mean", "gold_page_retrieved_rate",
        "hallucination_rate", "claims_lexically_supported_rate",
        "citation_validity_mean", "cites_gold_page_rate",
        "total_ms_median", "total_ms_mean", "retrieval_ms_median", "generation_ms_median",
    ]
    rows = []
    for cond in CONDITION_ORDER:
        agg = summary["by_condition"].get(cond)
        if not agg:
            continue
        special = {"no_rag": 0, "gold": "oracle"}
        k = special[cond] if cond in special else int(cond[1:])
        supported_rate = agg.get("claims_lexically_supported_rate")
        rows.append({
            "condition": cond,
            "label": CONDITION_LABEL[cond],
            "k": k,
            "n": agg["n"],
            "accuracy_normalised_mean": agg["accuracy_normalised_mean"],
            "abstention_rate": agg["abstention_rate"],
            "context_fact_recall_mean": agg["context_fact_recall_mean"],
            "context_fact_bearing_precision_mean": agg["context_fact_bearing_precision_mean"],
            "gold_page_retrieved_rate": agg["gold_page_retrieved_rate"],
            "hallucination_rate": round(1 - supported_rate, 4) if supported_rate is not None else None,
            "claims_lexically_supported_rate": supported_rate,
            "citation_validity_mean": agg["citation_validity_mean"],
            "cites_gold_page_rate": agg["cites_gold_page_rate"],
            "total_ms_median": agg["total_ms_median"],
            "total_ms_mean": agg["total_ms_mean"],
            "retrieval_ms_median": agg["retrieval_ms_median"],
            "generation_ms_median": agg["generation_ms_median"],
        })
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path} ({len(rows)} rows)")


def retrieval_rows(summary: dict) -> list[tuple[str, int, dict]]:
    """k1..k10 rows only, with numeric K, in order — the slice each chart plots."""
    out = []
    for cond in ["k1", "k3", "k5", "k10"]:
        agg = summary["by_condition"].get(cond)
        if agg:
            out.append((cond, int(cond[1:]), agg))
    return out


def make_figures(summary: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = retrieval_rows(summary)
    ks = [k for _, k, _ in rows]

    def line_chart(values, title, ylabel, filename, pct=False):
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.plot(ks, values, marker="o", color="#2563eb", linewidth=2)
        for x, y in zip(ks, values):
            if y is not None:
                label = f"{y:.0%}" if pct else f"{y:,.0f}"
                ax.annotate(label, (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
        ax.set_xlabel("K (retrieved chunks)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(ks)
        if pct:
            ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / filename, dpi=150)
        plt.close(fig)

    line_chart([agg["accuracy_normalised_mean"] for _, _, agg in rows],
               "Answer accuracy vs K", "Mean normalised accuracy (0-1)", "accuracy_vs_k.png", pct=True)
    line_chart([agg["context_fact_recall_mean"] for _, _, agg in rows],
               "Context relevance (fact recall) vs K", "Mean fact recall (0-1)", "context_relevance_vs_k.png", pct=True)
    line_chart([round(1 - agg["claims_lexically_supported_rate"], 4) for _, _, agg in rows],
               "Hallucination rate vs K", "Unsupported-claim rate (0-1)", "hallucination_rate_vs_k.png", pct=True)
    line_chart([agg["total_ms_median"] for _, _, agg in rows],
               "Response time vs K", "Median total latency (ms)", "response_time_vs_k.png", pct=False)
    print(f"wrote 4 figures to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_dir = Path("results/benchmark") / args.run_id
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    records = load_records(run_dir)

    results_dir = Path("results")
    write_results_csv(records, results_dir / "results.csv")
    write_comparison_table(summary, results_dir / "comparison_table.csv")
    make_figures(summary, results_dir / "figures")


if __name__ == "__main__":
    main()
