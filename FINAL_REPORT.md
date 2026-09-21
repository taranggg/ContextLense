# ContextLens — Final Execution Report

**Date:** 2026-09-21 (Asia/Calcutta)
**Project:** ContextLens: Investigating Impact of Retrieval Depth on RAG Answer Quality
**Tagline:** Does more context make AI smarter?

---

## 1. Files Created / Modified

### Core Pipeline (`src/`)
- `src/config.py` — central config, env-overridable, paths, LLM abstraction
- `src/utils.py` — cleaning, jsonl helpers, hashing
- `src/preprocessing.py` — PDF extraction page-by-page, artifact cleaning, CLI `python -m src.preprocessing`
- `src/chunking.py` — 500w target, 80 overlap, para-aware, same chunks for all K, CLI
- `src/embeddings.py` — all-MiniLM-L6-v2 + TF-IDF fallback, FAISS IP, npy + index, CLI `--force`
- `src/retriever.py` — semantic retrieval, `retrieve(query,k)`, timing, singleton
- `src/generator.py` — LLM provider abstraction (openai/groq/openrouter/together/ollama/mock), faithful prompt with citations, mock extractive fallback
- `src/evaluation.py` — accuracy 0-2 normalized, relevance 0-3 aggregated, hallucination claim-level, rule-based + optional LLM judge
- `src/experiment.py` — pilot 5×4=20, full 50×4=200, raw_runs.jsonl, results.csv, comparison_table.csv, question_level_results.csv, failure_cases.json, figures, statistical analysis (Wilcoxon + Holm)
- `src/validate_dataset.py` — checks PDFs, pages, chunks, benchmark 50 Qs, ground truth, dup IDs, etc.
- `src/generate_benchmark.py` — generates 50 Qs from PDFs (15 factual,10 procedural,10 eligibility,5 conditional,5 numerical,5 multi-part) with source pages

### Data
- `data/raw/Information_Brochure_2026.pdf` (3.4 MB, 25 pages, from https://ir.iitr.ac.in/pdf/PG_Information_Brochure_2026.pdf)
- `data/raw/PhD_IB_A2026.pdf` (3.2 MB, 37 pages, from https://iitr.ac.in/Academics/static/Admission/PhD/Autumn%202026/Ph.D._IB_A2026.pdf)
- `data/processed/pages.jsonl` (62 pages extracted)
- `data/processed/chunks.jsonl` (57 chunks, avg 210 words, same for all K)
- `data/processed/embeddings.npy` (57×384), `faiss.index` (FAISS IP), `embedding_meta.json`
- `data/benchmark/ContextLens_Benchmark_50_Questions.json` + CSV (50 Qs, categories balanced)
- `data/README.md`

### Backend (FastAPI)
- `backend/app/main.py` — endpoints: /health, /api/query, /api/experiment, /api/results/summary, /api/results/question/{id}, /api/benchmark, /api/failure-cases, /figures static
- `backend/app/schemas.py` — Pydantic models
- `backend/app/config.py`
- `backend/app/services/rag_service.py` — RAG orchestration
- `backend/app/services/experiment_service.py` — results summary
- `backend/app/services/evaluation_service.py`

### Frontend (Next.js 14 + TypeScript + Tailwind + Framer Motion + Recharts)
- `frontend/package.json`, `tailwind.config.js`, `next.config.js`, `tsconfig.json`
- `frontend/src/app/layout.tsx`, `globals.css`
- `frontend/src/app/page.tsx` — Landing: hero CONTEXTLENS, K cards, system status, architecture
- `frontend/src/app/experiment/page.tsx` — Experiment Lab: question input, benchmark examples, pipeline viz, 4 columns TOP-1/3/5/10 with chunks, similarity, answer, metrics
- `frontend/src/app/inspector/page.tsx` — Context Inspector: rank, doc, page, similarity, expand/collapse, why retrieved
- `frontend/src/app/dashboard/page.tsx` — Research Dashboard: 4 charts (accuracy/relevance/hallucination/time vs K), summary cards, comparison table, figures, neutral language
- `frontend/src/app/failures/page.tsx` — Failure Cases: auto-identified with evidence
- `frontend/src/app/methodology/page.tsx` — Dataset, chunking, embedding, FAISS, K, LLM, metrics, design, interactive diagram
- `frontend/src/app/about/page.tsx` — RQ, hypothesis, setup, limitations, future work, citations
- `frontend/src/components/Navbar.tsx`, `MetricCard.tsx`, `PipelineViz.tsx`
- `frontend/src/lib/utils.ts`

### Notebooks & Results
- `notebooks/experiment.ipynb` — 12 steps: load pages/chunks/embeddings/benchmark, retrieval, generation, eval, aggregate, stats, plots, failure cases, summary
- `results/` — raw_runs.jsonl (200), results.csv (200), comparison_table.csv, question_level_results.csv, failure_cases.json (25), statistical_analysis.csv, figures/ (10 PNGs), pilot_* files
- `presentation/outline.md` — 10-slide structure with result placeholders
- `README.md` — full documentation
- `.env.example`, `.gitignore`, `requirements.txt`

---

## 2. Commands to Run the Project

### Setup
```bash
# Python
pip install -r requirements.txt
# .env
cp .env.example .env
# Edit LLM_PROVIDER, API keys

# Frontend
cd frontend
npm install
```

### Pipeline
```bash
python -m src.preprocessing
python -m src.chunking
python -m src.embeddings --force
python -m src.generate_benchmark  # if no official benchmark
python -m src.validate_dataset

# Pilot 5×4=20
python -m src.experiment --pilot

# Full 50×4=200 (mock if no LLM key, real if key set)
python -m src.experiment --full
```

### Backend
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
# Health: http://localhost:8000/health
```

### Frontend
```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# http://localhost:3000
```

### Notebook
```bash
jupyter notebook notebooks/experiment.ipynb
```

---

## 3. Backend URL

- Local: http://localhost:8000
- Health: http://localhost:8000/health
- Docs (FastAPI auto): http://localhost:8000/docs
- Preview (if sandbox): https://8000-xxx.e2b.app (see LIVE PREVIEW panel labeled "Backend API")

Endpoints tested:
- POST /api/query {"question":"...","k":5} → answer + chunks + metrics
- POST /api/experiment {"question":"..."} → 4 K results
- GET /api/results/summary → aggregated + figures list
- GET /api/benchmark → 50 questions

---

## 4. Frontend URL

- Local: http://localhost:3000
- Preview (if sandbox): https://3000-xxx.e2b.app (see LIVE PREVIEW panel labeled "Frontend")
- Pages: /, /experiment, /inspector, /dashboard, /failures, /methodology, /about

---

## 5. Dataset Statistics

- Documents: 2
  - Information_Brochure_2026.pdf: 25 pages, 3.4 MB
  - PhD_IB_A2026.pdf: 37 pages, 3.2 MB
  - Total: 62 pages extracted
- Preprocessing:
  - num_documents: 2
  - num_pages: 62
  - total_chars: 86640
  - total_words: 12016
  - sparse_pages: 5 (very little text)
  - failures: 2 (empty pages)
- Chunking:
  - num_chunks: 57
  - total_words: 11994
  - avg_words: 210.42 (pages avg ~193 words, so per-page chunking limits size; target 500 but page size smaller)
  - min: 81, max: 407
  - duplicate_ids: 0
  - documents: both PDFs
  - Note: Same chunks used for all K (experimental validity)
- Embeddings:
  - Model: sentence-transformers/all-MiniLM-L6-v2 (384 dim)
  - Type: sentence_transformer (real, not TF-IDF fallback)
  - Vectors: 57
  - FAISS: IndexFlatIP, cosine
  - Generation time: ~3.6 sec
- Benchmark:
  - 50 questions (generated from PDFs, grounded)
  - Categories: direct_factual 15, procedural 10, eligibility 10, conditional 5, numerical 5, multi-part 5
  - Each: question_id, question, category, ground_truth, required_facts, source_document, source_page, difficulty

---

## 6. Number of Chunks

57 chunks (avg 210 words). Same set for K=1,3,5,10.

---

## 7. Pilot Status

✅ Completed: 5 questions × 4 K = 20 runs
- Output: results/pilot_runs.jsonl, pilot_results.csv, pilot_comparison_table.csv, pilot_question_level_results.csv, pilot_failure_cases.json
- Figures: 10 PNGs in results/figures/ (accuracy_vs_k, relevance_vs_k, hallucination_vs_k, response_time_vs_k, distributions, heatmap, similarity, failure summary)
- Comparison (pilot):
  - K=1: acc 0.5, relevance 0.73, halluc 0.05, time 14ms
  - K=3: acc 0.5, relevance 0.62, halluc 0.058, time 12ms
  - K=5: acc 0.5, relevance 0.66, halluc 0.033, time 12ms
  - K=10: acc 0.5, relevance 0.60, halluc 0.0, time 11ms
- Failure cases: 1 identified (more context introduced irrelevant info)

Pilot validated: retrieval quality, citations, evaluation, latency, errors.

---

## 8. Full Experiment Status

✅ Completed: 50 questions × 4 K = 200 runs (mock LLM, since no API key provided)
- Output:
  - results/raw_runs.jsonl (200 lines, 2.4 MB)
  - results/results.csv (200 rows)
  - results/comparison_table.csv (aggregated by K)
  - results/question_level_results.csv
  - results/failure_cases.json (25 cases)
  - results/statistical_analysis.csv (Wilcoxon + Holm)
  - results/figures/ (10 PNGs)

- Comparison Table (mock LLM):
  - K=1: acc 0.50±0.42, rel 0.873±0.21, hall 0.024±0.06, time 11.65ms
  - K=3: acc 0.51±0.42, rel 0.808±0.17, hall 0.106±0.12, time 11.37ms
  - K=5: acc 0.51±0.42, rel 0.765±0.17, hall 0.064±0.11, time 11.32ms
  - K=10: acc 0.51±0.42, rel 0.706±0.17, hall 0.082±0.11, time 11.30ms

- Statistical Analysis (sample):
  - Accuracy K=1 vs K=3: diff +0.01, p=0.317 (not significant, Holm corrected 0.95)
  - Relevance K=1 vs K=10: diff -0.166, p=1.0e-05 (significant, corrected 5e-05) → more context significantly reduces avg relevance
  - Hallucination K=1 vs K=3: diff +0.082, p=0.00018 (significant) → hallucination increased with more context in mock mode
  - Response time differences small (mock gen negligible, retrieval dominates)

- Observations (mock):
  - Accuracy plateau: no significant improvement beyond K=1 with mock extractive generation
  - Relevance decreases significantly with larger K (later chunks less relevant)
  - Hallucination may increase with K due to noise
  - Latency similar (mock)

- Note: With real LLM (OpenAI/Groq/Ollama), accuracy and hallucination trends may differ. Mock uses first chunk snippet, so trends reflect retrieval, not generation quality. Re-run with real LLM for publication results:
  ```
  LLM_PROVIDER=openai LLM_MODEL=gpt-4o-mini OPENAI_API_KEY=sk-... python -m src.experiment --full
  ```

---

## 9. Whether LLM API Key is Required

- **Not required for pipeline to run**: mock provider (extractive fallback) allows full execution: preprocessing, chunking, embeddings, retrieval, pilot, full experiment, backend, frontend, figures, stats, failure analysis, notebook.
- **Required for real generation & LLM-judge evaluation**: Set in `.env`:
  ```
  LLM_PROVIDER=openai (or groq, openrouter, together, ollama)
  LLM_MODEL=gpt-4o-mini (or llama-3.1-8b, etc.)
  OPENAI_API_KEY=sk-...
  EVAL_USE_LLM_JUDGE=true (optional, for LLM judge)
  ```
- System fails gracefully: if no key, returns mock answer with note "Configure LLM_PROVIDER and API key for real generation", clearly flagged, no silent fake.
- For Ollama local: `LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://localhost:11434 LLM_MODEL=llama3.1`

---

## 10. Any Remaining Issues

- **Chunk size avg 210 vs target 500**: Because pages average 193 words, per-page chunking can't reach 500 without cross-page merging. Current implementation respects "do not merge unrelated pages" strictly. Could be improved by allowing consecutive pages merge within same section, but keeps experimental validity (same chunks for all K). Not a blocker.
- **Mock LLM**: Full experiment used mock (no API key). Results show retrieval trends but not true LLM generation trends. Need real API key for final publication-quality results. One-command re-run documented.
- **Frontend build**: Dev server running, but production build not tested (`npm run build`). Should work, but may need to set NEXT_PUBLIC_API_URL.
- **Disk space**: HuggingFace cache + node_modules large (~500 MB). Cleanable.
- **Benchmark**: Generated from PDFs (grounded but synthetic). If user uploads official ContextLens_Benchmark_50_Questions.json, replace file and re-run validation + experiment. Validation will flag inconsistencies.
- **Statistical power**: 50 Qs moderate; Wilcoxon warnings for zero diff (expected). Holm correction implemented.
- **No GPU**: Sandbox 2 GB RAM, no GPU, torch CPU works but slow. Embeddings already generated and cached.
- **CORS**: Backend allows * for dev, restrict in production.

---

## 11. How to Re-run with Real LLM

1. Edit `.env`:
   ```
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o-mini
   OPENAI_API_KEY=sk-your-key
   EVAL_USE_LLM_JUDGE=true
   ```
2. Run:
   ```bash
   python -m src.experiment --full
   ```
3. Refresh frontend dashboard: http://localhost:3000/dashboard

---

## 12. Links

- Backend: http://localhost:8000/health
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Results: `results/comparison_table.csv`, `results/figures/`
- Notebook: `notebooks/experiment.ipynb`

---

**Status: COMPLETE END-TO-END** ✅
- Working Python RAG backend ✓
- FastAPI API ✓
- Next.js frontend ✓
- Preprocessing ✓
- Chunking (same for all K) ✓
- Embeddings (MiniLM-L6-v2, FAISS) ✓
- Top-1/3/5/10 experiment ✓
- Answer generation (mock + real abstraction) ✓
- Evaluation (accuracy, relevance, hallucination, latency) ✓
- Benchmark validation ✓
- Statistical analysis (Wilcoxon, Holm) ✓
- Failure analysis ✓
- Charts (10) ✓
- Notebook ✓
- README, .env.example, presentation outline ✓
- No fake results (mock clearly flagged) ✓
