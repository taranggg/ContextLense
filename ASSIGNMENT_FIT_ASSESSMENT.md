# Assignment Fit Assessment — ContextLens vs. RAG Mini-Project Brief

> **Update (resolved):** the packaging gaps below (§2–3) have been closed — real results.csv,
> comparison_table.csv, figures/, notebooks/experiment.ipynb and presentation/16_ContextLens.pptx now
> exist, generated from the actual 275-run benchmark (`results/benchmark/full-50q-2026-10-12/`), and
> the repo root was renamed to `MTech-AIML-Project_16_ContextLens/`. See [§5](#5-status-closed) for
> what changed and how to regenerate it. The rest of this file is kept as the original audit record.

## Verdict

The **research substance is strong and already exceeds the brief** — real RAG pipeline, real K-sweep
(1/3/5/10), all four required metrics instrumented, paired statistical testing (Wilcoxon + Holm
correction), and a 50-question benchmark with per-question gold validation. This is more rigorous
than what the assignment asks for.

The **submission packaging does not yet match the required deliverable structure**, and the
analysis layer (aggregated CSVs, charts, the actual .pptx) hasn't been generated from the raw run
data yet. These are the gaps to close before submitting — not a redesign of the project.

---

## 1. Research requirements — met

| Brief requirement | Status | Evidence |
|---|---|---|
| RAG system on domain documents | ✅ | IIT Roorkee PG + PhD admission brochures (62 pages), FAISS + MiniLM + local MLX LLM |
| Retrieve different numbers of passages, same questions | ✅ | `k ∈ {1,3,5,10}` + `no_rag`/`gold` baselines, same chunking reused across all K ([backend/app/research/benchmark.py](backend/app/research/benchmark.py)) |
| Compare Top-1 vs Top-3 vs Top-5 vs Top-10 | ✅ | Exactly this grid, run per-question, paired design |
| Metric: Answer Accuracy | ✅ | `metrics.accuracy` — required-fact coverage score per answer |
| Metric: Context Relevance | ✅ | `metrics.context.fact_recall`, `fact_bearing_chunk_precision`, `gold_page_retrieved` |
| Metric: Hallucination Rate | ✅ | `metrics.claims` — per-claim supported/unsupported/contradicted via lexical heuristic |
| Metric: Response Time | ✅ | `latency.retrieval_ms`, `generation_ms`, `total_ms` |
| Investigate "does more context always help" | ✅ | This is the project's explicit research question (see [README.md](README.md)) |

This is genuinely a well-designed experiment (controlled variable = K only, paired statistics,
abstention handling, citation validity) — better than a typical mini-project.

---

## 2. Required repo structure — gaps

The brief specifies:

```
MTech-AIML-Project_<GroupNo>_<ProjectName>/
├── README.md
├── requirements.txt
├── data/{README.md, sample_data.csv}
├── notebooks/experiment.ipynb
├── src/{preprocessing.py, model.py, evaluation.py}
├── results/{results.csv, comparison_table.csv, figures/}
└── presentation/GroupNumber_Project_Name.pptx
```

Current repo (`ContextLense/`):

| Required item | Current state | Gap |
|---|---|---|
| Root folder name `MTech-AIML-Project_<GroupNo>_<ProjectName>` | `ContextLense/` | Needs renaming (or a copy/export) for submission |
| `README.md` | ✅ present, thorough | none |
| `requirements.txt` | ✅ present | none |
| `data/README.md` | ✅ present | none |
| `data/sample_data.csv` | ❌ missing — has PDFs + `ContextLens_Benchmark_50_Questions.csv/json` instead | Rename/symlink the benchmark CSV, or add a short note mapping it to the expected name |
| `notebooks/experiment.ipynb` | ❌ does not exist — all logic lives in `backend/app/research/benchmark.py`, a CLI script | **Missing.** Need a notebook that walks through the K-sweep experiment, even if it just calls the existing backend code and loads `runs.jsonl` for analysis/plots |
| `src/preprocessing.py`, `model.py`, `evaluation.py` | Exists but scattered across `backend/app/services/`, `backend/app/research/`, `backend/app/api/` under a full FastAPI app layout | Not a blocker technically, but doesn't match the expected flat `src/` module names. Consider adding thin `src/` wrapper modules, or explaining the mapping in the README |
| `results/results.csv` | ❌ only raw `runs.jsonl` + `config.json` exist; no aggregated CSV generated yet | **Missing — need to run the aggregation step** |
| `results/comparison_table.csv` | ❌ not generated | **Missing** |
| `results/figures/` | ❌ no charts generated yet | **Missing — this is the biggest real gap** |
| `presentation/*.pptx` | ❌ only `presentation/outline.md` exists (good outline, not built) | **Missing — needs to actually be built as a .pptx** |

---

## 3. What's actually blocking submission (in priority order)

1. **Generate the aggregated results.** The code to do this already exists
   (`aggregate()`, `paired_tests()`, `summarize()` in [backend/app/research/benchmark.py](backend/app/research/benchmark.py:290-403))
   but hasn't been run to completion for this run directory — `results/benchmark/full-50q-2026-10-12/`
   has `runs.jsonl` and `config.json` but **no `summary.json`**, and there is no script that exports
   `results.csv` / `comparison_table.csv` from it. Need to either call `summarize()` and then write a
   small CSV exporter, or extend it directly.
2. **Generate `figures/`.** No charting code was found anywhere in the repo. Need accuracy/relevance/
   hallucination/response-time vs K charts with error bars — exactly what slide 7 of the presentation
   outline calls for.
3. **Build the actual `.pptx`.** The outline in `presentation/outline.md` is detailed and ready to use —
   it just needs to become a real file, populated with the real numbers once step 1–2 are done.
4. **Add `notebooks/experiment.ipynb`.** Even a notebook that imports from `backend/app/research/benchmark.py`,
   loads `runs.jsonl`, and reproduces the aggregation + charts inline would satisfy this without
   duplicating logic.
5. **Rename for submission.** Copy or rename the repo to `MTech-AIML-Project_<GroupNo>_ContextLens/`
   and reconcile the `data/`/`src/` naming gaps (lightweight — path aliases or a short note in the README
   explaining where each expected file lives).

## 4. What not to change

- Don't restructure the FastAPI app into the flat `src/` layout — that would be a regression for a
  project this size. A short note in the README mapping `src/preprocessing.py` → actual files is enough.
- Don't rewrite the research design — it already satisfies (and exceeds) the brief's hypothesis/metric
  requirements.
- Keep the "no fabricated results" discipline from the presentation outline notes — fill in real numbers
  only after step 1–2 produce them.

---

## 5. Status: closed

What was added, without restructuring `backend/`/`frontend/`:

| Item | How it was produced |
|---|---|
| `results/benchmark/full-50q-2026-10-12/summary.json` | Called the existing `summarize()` from `backend/app/research/benchmark.py` directly against the completed run (it's a pure function over `runs.jsonl` — no DB/LLM needed) |
| `results/results.csv` | New `scripts/export_results.py` — flattens all 275 per-question/per-condition records with every metric |
| `results/comparison_table.csv` | Same script — aggregates by condition (`no_rag`, `k1`, `k3`, `k5`, `k10`, `gold`) |
| `results/figures/*.png` | Same script — accuracy/context-relevance/hallucination/response-time vs K, via matplotlib |
| `notebooks/experiment.ipynb` | Loads `runs.jsonl`, reuses `aggregate()`/`paired_tests()` from the existing backend module (no duplicated logic), reproduces the same charts. Executed end-to-end with `jupyter execute` and saved with outputs |
| `presentation/16_ContextLens.pptx` | New `scripts/build_presentation.py` — builds the 10-slide deck from `presentation/outline.md`'s structure, populated with the real numbers from `comparison_table.csv` and the real chart PNGs |
| `data/sample_data.csv` | Copy of `data/benchmark/ContextLens_Benchmark_50_Questions.csv`, documented in `data/README.md` as a filename alias, not a second dataset |
| Root folder | Renamed `ContextLense/` → `MTech-AIML-Project_16_ContextLens/` |
| `requirements.txt` | Added `pandas`, `matplotlib`, `python-pptx`, `jupyter` under a "Submission tooling" section |

**The real result (worth knowing before the presentation):** accuracy rises sharply from K=1 (32%) to
K=3 (51%), then flattens toward K=10 (59%) — diminishing returns, as H1 predicted. Context relevance
and the lexically-supported-claim rate both rise monotonically with K (hallucination fell from 54% at
K=1 to 7% at K=10 on this dataset — the opposite of the "more noise" intuition). Response time grows
near-linearly with K (7s median at K=1 → 52s at K=10). The Gold-page oracle condition beat Top-10 on
both accuracy (72% vs 59%) and latency (3.7s vs 52s), suggesting retrieval precision matters more than
raw K. Paired Wilcoxon tests (Holm-corrected) are in `summary.json["paired_tests"]`.

**Not done / still manual:** `src/preprocessing.py`/`model.py`/`evaluation.py` were deliberately left
as-is inside `backend/app/` per your instruction not to restructure — the mapping is documented in §2
above. If a grader insists on the literal flat `src/` filenames, that's the one remaining judgment call.

**To regenerate after a new benchmark run:**
```bash
.venv/bin/python scripts/export_results.py --run-id <new-run-id>
.venv/bin/python scripts/build_presentation.py
# re-run notebooks/experiment.ipynb if RUN_ID changes
```
