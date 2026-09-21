"""
Controlled experiment: 50 questions x 4 K values = 200 runs.
Records: question, question_id, k, retrieved_chunks, generated_answer, timings, metrics.

Pilot: 5 questions x 4 K = 20 runs.
Main: 50 x 4 = 200 runs.

Outputs:
results/raw_runs.jsonl
results/results.csv
results/question_level_results.csv
results/comparison_table.csv
results/failure_cases.json
results/figures/*.png

CLI:
python -m src.experiment --pilot
python -m src.experiment --full
python -m src.experiment --pilot --k-values 1,3,5,10
"""
import json
import time
import csv
import argparse
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
import pandas as pd

from .config import BENCHMARK_PATH, RESULTS_DIR, FIGURES_DIR, TOP_K_VALUES
from .utils import load_json, save_jsonl, logger
from .retriever import get_retriever
from .generator import get_llm_provider
from .evaluation import evaluate_run

def load_benchmark() -> List[Dict]:
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"Benchmark not found: {BENCHMARK_PATH}. Run generate_benchmark first.")
    data = load_json(BENCHMARK_PATH)
    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    elif isinstance(data, list):
        questions = data
    else:
        raise ValueError("Benchmark JSON structure invalid")
    logger.info(f"Loaded {len(questions)} benchmark questions")
    return questions

def run_single_experiment(question_obj: Dict, k: int, retriever, llm_provider) -> Dict:
    q_id = question_obj.get("question_id")
    question = question_obj.get("question")
    ground_truth = question_obj.get("ground_truth","")
    required_facts = question_obj.get("required_facts",[])

    # Retrieval
    ret_start = time.perf_counter()
    retrieved_chunks = retriever.retrieve(question, k=k)
    retrieval_time_ms = (time.perf_counter() - ret_start) * 1000

    # Generation
    gen_start = time.perf_counter()
    answer, gen_time_ms, gen_meta = llm_provider.generate(question, retrieved_chunks)
    # If generate already measured time, use it; else compute
    if gen_time_ms is None:
        gen_time_ms = (time.perf_counter() - gen_start) * 1000

    total_time_ms = retrieval_time_ms + gen_time_ms

    # Evaluation
    eval_result = evaluate_run(question, ground_truth, required_facts, answer, retrieved_chunks)

    # Build record
    record = {
        "question_id": q_id,
        "question": question,
        "category": question_obj.get("category","unknown"),
        "ground_truth": ground_truth,
        "required_facts": required_facts,
        "k": k,
        "retrieved_chunks": retrieved_chunks,
        "retrieved_chunk_ids": [c["chunk_id"] for c in retrieved_chunks],
        "retrieved_documents": list(set(c["document"] for c in retrieved_chunks)),
        "retrieved_pages": [c["page"] for c in retrieved_chunks],
        "retrieval_time_ms": retrieval_time_ms,
        "generation_time_ms": gen_time_ms,
        "total_response_time_ms": total_time_ms,
        "generated_answer": answer,
        "answer": answer,  # alias for csv
        "answer_accuracy": eval_result.get("answer_accuracy",0),
        "context_relevance": eval_result.get("context_relevance",0),
        "hallucination_rate": eval_result.get("hallucination_rate",0),
        "answer_accuracy_raw": eval_result.get("answer_accuracy_raw",{}),
        "context_relevance_raw": eval_result.get("context_relevance_raw",{}),
        "hallucination_raw": eval_result.get("hallucination_raw",{}),
        "generation_meta": gen_meta,
        "source_documents": list(set(c["document"] for c in retrieved_chunks)),
        "source_pages": [c["page"] for c in retrieved_chunks],
    }
    return record

def run_experiment(questions: List[Dict], k_values: List[int], output_jsonl: Path, pilot: bool = False) -> List[Dict]:
    retriever = get_retriever()
    llm_provider = get_llm_provider()

    logger.info(f"Starting {'pilot' if pilot else 'full'} experiment: {len(questions)} questions x {k_values} = {len(questions)*len(k_values)} runs")
    logger.info(f"LLM Provider: {llm_provider.provider}, Model: {llm_provider.model}")

    all_results = []
    # Ensure results dir
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Open jsonl for streaming writes
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for q_obj in tqdm(questions, desc="Questions"):
            for k in k_values:
                try:
                    rec = run_single_experiment(q_obj, k, retriever, llm_provider)
                    all_results.append(rec)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()
                except Exception as e:
                    logger.error(f"Failed Q {q_obj.get('question_id')} k={k}: {e}")
                    # Record failure
                    err_rec = {
                        "question_id": q_obj.get("question_id"),
                        "question": q_obj.get("question"),
                        "k": k,
                        "error": str(e),
                        "retrieved_chunks": [],
                        "generated_answer": f"ERROR: {e}",
                        "answer": f"ERROR: {e}",
                        "retrieval_time_ms": 0,
                        "generation_time_ms": 0,
                        "total_response_time_ms": 0,
                        "answer_accuracy": 0,
                        "context_relevance": 0,
                        "hallucination_rate": 1.0,
                    }
                    all_results.append(err_rec)
                    f.write(json.dumps(err_rec, ensure_ascii=False) + "\n")

    logger.info(f"Saved raw runs to {output_jsonl}")
    return all_results

def results_to_csv(results: List[Dict], csv_path: Path):
    # Flatten for CSV
    rows = []
    for r in results:
        rows.append({
            "question_id": r.get("question_id"),
            "question": r.get("question"),
            "category": r.get("category"),
            "k": r.get("k"),
            "answer": r.get("answer","")[:5000],  # truncate for csv
            "retrieved_chunk_ids": ",".join(r.get("retrieved_chunk_ids",[])),
            "retrieved_documents": ",".join(r.get("retrieved_documents",[])),
            "retrieved_pages": ",".join(map(str, r.get("retrieved_pages",[]))),
            "retrieval_time_ms": r.get("retrieval_time_ms"),
            "generation_time_ms": r.get("generation_time_ms"),
            "total_response_time_ms": r.get("total_response_time_ms"),
            "answer_accuracy": r.get("answer_accuracy"),
            "context_relevance": r.get("context_relevance"),
            "hallucination_rate": r.get("hallucination_rate"),
        })
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved results CSV to {csv_path} with {len(df)} rows")
    return df

def generate_comparison_table(results: List[Dict], output_path: Path):
    df = pd.DataFrame(results)
    # Aggregate by k
    grouped = df.groupby("k").agg({
        "answer_accuracy": ["mean","std","median"],
        "context_relevance": ["mean","std","median"],
        "hallucination_rate": ["mean","std","median"],
        "total_response_time_ms": ["mean","std","median"],
        "retrieval_time_ms": ["mean","std"],
        "generation_time_ms": ["mean","std"],
    }).round(4)
    # Flatten columns
    grouped.columns = ["_".join(col).strip() for col in grouped.columns.values]
    grouped = grouped.reset_index()
    grouped.to_csv(output_path, index=False)
    logger.info(f"Saved comparison table to {output_path}")

    # Also print
    print("\n=== Comparison Table (Aggregated by K) ===")
    print(grouped.to_string(index=False))
    return grouped

def generate_question_level_results(results: List[Dict], output_path: Path):
    # Pivot: each question_id row, columns for each K metric
    df = pd.DataFrame(results)
    # Create wide format
    pivot_acc = df.pivot(index=["question_id","question","category"], columns="k", values="answer_accuracy").add_prefix("accuracy_k")
    pivot_rel = df.pivot(index=["question_id","question","category"], columns="k", values="context_relevance").add_prefix("relevance_k")
    pivot_hall = df.pivot(index=["question_id","question","category"], columns="k", values="hallucination_rate").add_prefix("hallucination_k")
    pivot_time = df.pivot(index=["question_id","question","category"], columns="k", values="total_response_time_ms").add_prefix("time_k")

    combined = pd.concat([pivot_acc, pivot_rel, pivot_hall, pivot_time], axis=1).reset_index()
    combined.to_csv(output_path, index=False)
    logger.info(f"Saved question-level results to {output_path}")
    return combined

def analyze_failure_cases(results: List[Dict], output_path: Path):
    """
    Identify interesting failure cases:
    - More context introduced irrelevant info (relevance decreases with K)
    - Top-1 missed supporting passage (accuracy low at K=1 but high at K>1)
    - Top-5 contradictory passages (hallucination increase)
    - Top-10 latency substantially higher
    - Correct context retrieved but LLM ignored
    - Unsupported claims
    - Duplicate chunks
    """
    from collections import defaultdict
    by_q = defaultdict(list)
    for r in results:
        by_q[r["question_id"]].append(r)

    failures = []

    for q_id, runs in by_q.items():
        runs_sorted = sorted(runs, key=lambda x: x["k"])
        # Map k->run
        k_map = {r["k"]: r for r in runs_sorted}
        question_text = runs_sorted[0]["question"]

        # Case 1: Top-1 missed but higher K better (accuracy)
        if 1 in k_map and 3 in k_map:
            acc1 = k_map[1]["answer_accuracy"]
            acc3 = k_map[3]["answer_accuracy"]
            if acc1 < 0.5 and acc3 >= 0.8:
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "Top-1 missed important passage",
                    "k": 1,
                    "observed": f"Accuracy K=1 {acc1} vs K=3 {acc3}",
                    "answer_k1": k_map[1]["answer"],
                    "answer_k3": k_map[3]["answer"],
                    "metrics": {k: {"accuracy": k_map[k]["answer_accuracy"], "relevance": k_map[k]["context_relevance"], "hallucination": k_map[k]["hallucination_rate"]} for k in k_map},
                    "explanation": "Top-1 retrieval missed supporting passage that was present in Top-3, leading to higher accuracy with more context."
                })

        # Case 2: More context introduced irrelevant info (relevance decreases)
        if 1 in k_map and 10 in k_map:
            rel1 = k_map[1]["context_relevance"]
            rel10 = k_map[10]["context_relevance"]
            if rel1 > rel10 + 0.3:  # significant drop
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "More context introduced irrelevant information",
                    "k": 10,
                    "observed": f"Relevance K=1 {rel1:.2f} vs K=10 {rel10:.2f}",
                    "answer": k_map[10]["answer"],
                    "retrieved_context": [c["text"][:300] for c in k_map[10]["retrieved_chunks"]],
                    "metrics": {k: {"relevance": k_map[k]["context_relevance"]} for k in k_map},
                    "explanation": "Adding more chunks decreased average relevance, suggesting later retrieved chunks were less relevant and potentially added noise."
                })

        # Case 3: Hallucination increase with K
        if 1 in k_map and 10 in k_map:
            h1 = k_map[1]["hallucination_rate"]
            h10 = k_map[10]["hallucination_rate"]
            if h10 > h1 + 0.3:
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "Hallucination increased with more context",
                    "k": 10,
                    "observed": f"Hallucination K=1 {h1:.2f} vs K=10 {h10:.2f}",
                    "answer_k1": k_map[1]["answer"],
                    "answer_k10": k_map[10]["answer"],
                    "metrics": {k: {"hallucination": k_map[k]["hallucination_rate"]} for k in k_map},
                    "explanation": "More context led to higher hallucination rate, possibly due to contradictory passages or LLM confusion."
                })

        # Case 4: Latency substantial increase
        if 1 in k_map and 10 in k_map:
            t1 = k_map[1]["total_response_time_ms"]
            t10 = k_map[10]["total_response_time_ms"]
            if t10 > t1 * 2 and t10 > 2000:
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "Top-10 increased latency substantially",
                    "k": 10,
                    "observed": f"Latency K=1 {t1:.0f}ms vs K=10 {t10:.0f}ms",
                    "metrics": {k: {"total_time": k_map[k]["total_response_time_ms"]} for k in k_map},
                    "explanation": "Larger K increases both retrieval and generation time, especially generation due to longer prompt."
                })

        # Case 5: Unsupported claims (hallucination >0)
        for k in k_map:
            if k_map[k]["hallucination_rate"] > 0.5:
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "Answer contained unsupported claims",
                    "k": k,
                    "observed": f"Hallucination rate {k_map[k]['hallucination_rate']:.2f} at K={k}",
                    "answer": k_map[k]["answer"],
                    "retrieved_context": [c["text"][:300] for c in k_map[k]["retrieved_chunks"]],
                    "metrics": {"hallucination": k_map[k]["hallucination_rate"], "accuracy": k_map[k]["answer_accuracy"]},
                    "explanation": "Generated answer contained claims not supported by retrieved context."
                })
                break  # only one per question to avoid flooding

        # Case 6: Correct context retrieved but LLM ignored (high relevance but low accuracy)
        for k in k_map:
            rel = k_map[k]["context_relevance"]
            acc = k_map[k]["answer_accuracy"]
            if rel >= 0.7 and acc <= 0.3:
                failures.append({
                    "question_id": q_id,
                    "question": question_text,
                    "failure_type": "Correct context retrieved but LLM ignored it",
                    "k": k,
                    "observed": f"Relevance {rel:.2f} but Accuracy {acc:.2f} at K={k}",
                    "answer": k_map[k]["answer"],
                    "retrieved_context": [c["text"][:300] for c in k_map[k]["retrieved_chunks"]],
                    "metrics": {"relevance": rel, "accuracy": acc},
                    "explanation": "Retrieved chunks were relevant but LLM failed to use them to generate correct answer, possibly due to prompt or generation issue."
                })
                break

    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(failures, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(failures)} failure cases to {output_path}")
    print(f"\n=== Failure Cases: {len(failures)} identified ===")
    for fc in failures[:5]:
        print(f"- {fc['question_id']} | {fc['failure_type']} | K={fc.get('k')}")
    return failures

def generate_visualizations(results: List[Dict]):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
        import pandas as pd
    except Exception as e:
        logger.warning(f"Visualization dependencies missing: {e}")
        return

    df = pd.DataFrame(results)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Set style
    plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')
    sns.set_palette("deep")

    k_order = sorted(df["k"].unique())

    # 1. Answer Accuracy vs K
    plt.figure(figsize=(8,5))
    acc_by_k = df.groupby("k")["answer_accuracy"].agg(["mean","std"]).reindex(k_order)
    plt.errorbar(acc_by_k.index, acc_by_k["mean"], yerr=acc_by_k["std"], marker='o', capsize=5, linewidth=2)
    plt.title("Answer Accuracy vs Retrieval Depth K")
    plt.xlabel("K (retrieved chunks)")
    plt.ylabel("Mean Answer Accuracy (normalized 0-1)")
    plt.xticks(k_order)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "accuracy_vs_k.png", dpi=200)
    plt.close()

    # 2. Context Relevance vs K
    plt.figure(figsize=(8,5))
    rel_by_k = df.groupby("k")["context_relevance"].agg(["mean","std"]).reindex(k_order)
    plt.errorbar(rel_by_k.index, rel_by_k["mean"], yerr=rel_by_k["std"], marker='s', capsize=5, linewidth=2, color='green')
    plt.title("Context Relevance vs Retrieval Depth K")
    plt.xlabel("K")
    plt.ylabel("Mean Context Relevance")
    plt.xticks(k_order)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "relevance_vs_k.png", dpi=200)
    plt.close()

    # 3. Hallucination Rate vs K
    plt.figure(figsize=(8,5))
    hall_by_k = df.groupby("k")["hallucination_rate"].agg(["mean","std"]).reindex(k_order)
    plt.errorbar(hall_by_k.index, hall_by_k["mean"], yerr=hall_by_k["std"], marker='^', capsize=5, linewidth=2, color='red')
    plt.title("Hallucination Rate vs Retrieval Depth K")
    plt.xlabel("K")
    plt.ylabel("Mean Hallucination Rate")
    plt.xticks(k_order)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "hallucination_vs_k.png", dpi=200)
    plt.close()

    # 4. Response Time vs K
    plt.figure(figsize=(8,5))
    time_by_k = df.groupby("k")["total_response_time_ms"].agg(["mean","std"]).reindex(k_order)
    plt.errorbar(time_by_k.index, time_by_k["mean"], yerr=time_by_k["std"], marker='d', capsize=5, linewidth=2, color='purple')
    plt.title("Response Time vs Retrieval Depth K")
    plt.xlabel("K")
    plt.ylabel("Mean Total Response Time (ms)")
    plt.xticks(k_order)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "response_time_vs_k.png", dpi=200)
    plt.close()

    # 5. Accuracy distribution by K
    plt.figure(figsize=(10,5))
    sns.boxplot(data=df, x="k", y="answer_accuracy")
    plt.title("Accuracy Distribution by K")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "accuracy_distribution_by_k.png", dpi=200)
    plt.close()

    # 6. Hallucination distribution
    plt.figure(figsize=(10,5))
    sns.boxplot(data=df, x="k", y="hallucination_rate", color="lightcoral")
    plt.title("Hallucination Distribution by K")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "hallucination_distribution_by_k.png", dpi=200)
    plt.close()

    # 7. Response time distribution
    plt.figure(figsize=(10,5))
    sns.boxplot(data=df, x="k", y="total_response_time_ms", color="lightblue")
    plt.title("Response Time Distribution by K")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "response_time_distribution_by_k.png", dpi=200)
    plt.close()

    # 8. Question-level K comparison (heatmap for first 20 questions accuracy)
    try:
        pivot = df.pivot(index="question_id", columns="k", values="answer_accuracy")
        # Sort by question_id
        pivot = pivot.sort_index()
        plt.figure(figsize=(10,8))
        sns.heatmap(pivot.iloc[:20], annot=True, cmap="YlGnBu", vmin=0, vmax=1)
        plt.title("Question-Level Accuracy (first 20 Qs) vs K")
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / "question_level_k_comparison.png", dpi=200)
        plt.close()
    except Exception as e:
        logger.warning(f"Failed heatmap: {e}")

    # 9. Retrieval similarity distribution
    try:
        # Extract similarities from retrieved_chunks
        sims = []
        ks = []
        for r in results:
            for c in r.get("retrieved_chunks",[]):
                sims.append(c.get("similarity",0))
                ks.append(r["k"])
        sim_df = pd.DataFrame({"similarity": sims, "k": ks})
        plt.figure(figsize=(10,5))
        sns.histplot(data=sim_df, x="similarity", hue="k", bins=30, kde=True, element="step")
        plt.title("Retrieval Similarity Distribution by K")
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / "retrieval_similarity_distribution.png", dpi=200)
        plt.close()
    except Exception as e:
        logger.warning(f"Failed similarity distribution: {e}")

    # 10. Failure case summary (if exists)
    failure_path = RESULTS_DIR / "failure_cases.json"
    if failure_path.exists():
        try:
            with open(failure_path) as f:
                failures = json.load(f)
            from collections import Counter
            types = Counter([fc["failure_type"] for fc in failures])
            plt.figure(figsize=(10,6))
            plt.bar(types.keys(), types.values(), color='tomato')
            plt.xticks(rotation=30, ha='right')
            plt.title("Failure Case Summary")
            plt.ylabel("Count")
            plt.tight_layout()
            plt.savefig(FIGURES_DIR / "failure_case_summary.png", dpi=200)
            plt.close()
        except Exception as e:
            logger.warning(f"Failed failure case summary plot: {e}")

    logger.info(f"Saved visualizations to {FIGURES_DIR}")
    print(f"\nVisualizations saved to {FIGURES_DIR}")

def statistical_analysis(results: List[Dict], output_path: Path):
    try:
        import pandas as pd
        from scipy.stats import wilcoxon
        import numpy as np
    except Exception as e:
        logger.warning(f"Statistical analysis dependencies missing: {e}")
        return

    df = pd.DataFrame(results)
    # Paired comparisons: same question at different K
    # We'll compare K=1 vs 3, 1 vs 5, 1 vs 10, 3 vs 5 etc for each metric
    comparisons = [(1,3),(1,5),(1,10),(3,5),(3,10),(5,10)]
    metrics = ["answer_accuracy","context_relevance","hallucination_rate","total_response_time_ms"]

    rows = []
    for metric in metrics:
        for k1,k2 in comparisons:
            # pivot to get paired values
            try:
                pivot = df.pivot(index="question_id", columns="k", values=metric)
                if k1 not in pivot.columns or k2 not in pivot.columns:
                    continue
                # drop na
                paired = pivot[[k1,k2]].dropna()
                if len(paired) < 5:
                    continue
                x = paired[k1].values
                y = paired[k2].values
                # Wilcoxon
                try:
                    stat, p = wilcoxon(x, y)
                except Exception:
                    stat, p = None, None
                # effect size: mean diff
                mean_diff = float(np.mean(y - x))
                # direction
                if mean_diff > 0:
                    direction = f"K={k2} higher than K={k1}"
                elif mean_diff < 0:
                    direction = f"K={k2} lower than K={k1}"
                else:
                    direction = "no difference"

                rows.append({
                    "metric": metric,
                    "k1": k1,
                    "k2": k2,
                    "n": len(paired),
                    "mean_k1": float(np.mean(x)),
                    "mean_k2": float(np.mean(y)),
                    "mean_diff": mean_diff,
                    "direction": direction,
                    "wilcoxon_stat": stat,
                    "p_value": p,
                })
            except Exception as e:
                logger.warning(f"Failed comparison {metric} {k1} vs {k2}: {e}")

    # Holm correction per metric
    try:
        from statsmodels.stats.multitest import multipletests
        has_statsmodels = True
    except ImportError:
        has_statsmodels = False
        # simple Holm implementation
        def holm_correct(pvals):
            # sort
            sorted_idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
            corrected = [0]*len(pvals)
            m = len(pvals)
            for rank, idx in enumerate(sorted_idx):
                corrected[idx] = min(1.0, pvals[idx] * (m - rank))
            return corrected

    # Apply correction grouped by metric
    if rows:
        df_stats = pd.DataFrame(rows)
        corrected_ps = []
        for metric in metrics:
            sub = df_stats[df_stats["metric"]==metric]
            pvals = sub["p_value"].dropna().tolist()
            if not pvals:
                continue
            if has_statsmodels:
                _, p_corr, _, _ = multipletests(pvals, method='holm')
            else:
                p_corr = holm_correct(pvals)
            # map back
            idx = 0
            for i,row in df_stats.iterrows():
                if row["metric"]==metric and row["p_value"] is not None and not pd.isna(row["p_value"]):
                    corrected_ps.append((i, p_corr[idx]))
                    idx+=1
        # add corrected
        df_stats["p_corrected"] = None
        for i, pc in corrected_ps:
            df_stats.at[i, "p_corrected"] = pc

        df_stats.to_csv(output_path, index=False)
        logger.info(f"Saved statistical analysis to {output_path}")
        print(f"\n=== Statistical Analysis (sample) ===")
        print(df_stats.head(10).to_string(index=False))
        return df_stats

def main():
    parser = argparse.ArgumentParser(description="ContextLens Experiment Runner")
    parser.add_argument("--pilot", action="store_true", help="Run pilot: 5 questions x 4 K")
    parser.add_argument("--full", action="store_true", help="Run full: 50 questions x 4 K")
    parser.add_argument("--k-values", type=str, default=",".join(map(str, TOP_K_VALUES)), help="Comma-separated K values")
    parser.add_argument("--questions", type=int, default=None, help="Limit number of questions (for testing)")
    args = parser.parse_args()

    k_values = [int(x.strip()) for x in args.k_values.split(",") if x.strip()]

    # Load benchmark
    questions = load_benchmark()
    if args.questions:
        questions = questions[:args.questions]

    if args.pilot:
        questions = questions[:5]
        output_jsonl = RESULTS_DIR / "pilot_runs.jsonl"
        results = run_experiment(questions, k_values, output_jsonl, pilot=True)
        # Generate outputs
        results_to_csv(results, RESULTS_DIR / "pilot_results.csv")
        generate_comparison_table(results, RESULTS_DIR / "pilot_comparison_table.csv")
        generate_question_level_results(results, RESULTS_DIR / "pilot_question_level_results.csv")
        analyze_failure_cases(results, RESULTS_DIR / "pilot_failure_cases.json")
        generate_visualizations(results)
        print("\nPilot experiment completed!")
        print(f"Raw: {output_jsonl}")
        print(f"Results dir: {RESULTS_DIR}")

    elif args.full:
        output_jsonl = RESULTS_DIR / "raw_runs.jsonl"
        results = run_experiment(questions, k_values, output_jsonl, pilot=False)
        results_to_csv(results, RESULTS_DIR / "results.csv")
        generate_comparison_table(results, RESULTS_DIR / "comparison_table.csv")
        generate_question_level_results(results, RESULTS_DIR / "question_level_results.csv")
        failures = analyze_failure_cases(results, RESULTS_DIR / "failure_cases.json")
        generate_visualizations(results)
        statistical_analysis(results, RESULTS_DIR / "statistical_analysis.csv")
        print("\nFull experiment completed!")
        print(f"Total runs: {len(results)}")
        print(f"Results: {RESULTS_DIR / 'results.csv'}")
        print(f"Comparison: {RESULTS_DIR / 'comparison_table.csv'}")
        print(f"Failures: {RESULTS_DIR / 'failure_cases.json'}")
    else:
        print("Specify --pilot or --full")
        parser.print_help()

if __name__ == "__main__":
    main()
