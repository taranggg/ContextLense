# ContextLens: Investigating the Impact of Retrieval Depth on RAG Answer Quality

**Tagline:** *Does more context make AI smarter?*

> Does increasing the number of retrieved chunks in a Retrieval-Augmented Generation (RAG) system always improve answer quality?

This M.Tech Modern AI mini-project experimentally compares **Top-1 vs Top-3 vs Top-5 vs Top-10** retrieved chunks and measures:

1. **Answer Accuracy** (0-2 → normalized 0-1)
2. **Context Relevance** (0-3 per chunk → aggregated)
3. **Hallucination Rate** (claim-level SUPPORTED/UNSUPPORTED/CONTRADICTED)
4. **Response Time** (retrieval, generation, total)

**Critical rule:** Only K changes. Everything else constant: same documents, same preprocessing, same chunks, same embedding model, same FAISS index, same similarity metric, same questions, same ground truth, same LLM, same prompt, same generation params, same eval methodology.

---

## 1. Motivation

RAG systems retrieve top-K chunks to augment LLM generation. Common assumption: more context = better answer. But more context can introduce irrelevant information, contradictory passages, increased latency, and LLM confusion. This project tests that assumption empirically on IIT Roorkee academic documents.

## 2. Dataset

- **Information_Brochure_2026.pdf**: 25 pages, PG admissions (M.Tech/M.Arch/MURP), eligibility, sponsored categories, application process. Source: https://ir.iitr.ac.in/pdf/PG_Information_Brochure_2026.pdf
- **PhD_IB_A2026.pdf**: 37 pages, PhD admission requirements, departments, MEQ, categories FTRS/PTRS/Golden Girl. Source: https://iitr.ac.in/Academics/static/Admission/PhD/Autumn%202026/Ph.D._IB_A2026.pdf

Total: 62 pages, 2 documents.

### Benchmark (50 Questions)

- 15 direct factual
- 10 procedural
- 10 eligibility
- 5 conditional
- 5 numerical
- 5 multi-part

Each question has: question_id, question, category, ground_truth, required_facts, source_document, source_page, difficulty.

Location: `data/benchmark/ContextLens_Benchmark_50_Questions.json` + CSV.

If you have the official benchmark, replace the generated one. Validation will flag inconsistencies.

## 3. Architecture

```
PDFs → Preprocessing (pypdf, cleaning) → Pages JSONL
→ Chunking (500w, 80 overlap, para-aware) → Chunks JSONL (same for all K)
→ Embeddings (all-MiniLM-L6-v2, 384d, FAISS IP) → embeddings.npy + faiss.index
→ Retrieval (query embedding, top-K, cosine) → Ranked chunks + similarity
→ Generation (LLM, faithful, cited) → Answer + sources
→ Evaluation (accuracy, relevance, hallucination, latency)
→ Comparison & Stats (Wilcoxon, Holm)
```

## 4. RAG Pipeline

- **Preprocessing**: page-by-page extraction, preserve doc name + page number, clean artifacts, fix hyphenated breaks, preserve paragraphs, store `data/processed/pages.jsonl`
- **Chunking**: ~500 words, ~80 overlap, semantic/paragraph boundaries, same chunks for all K, store `chunks.jsonl`
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2, configurable, efficient storage, not recomputed each start, FAISS IndexFlatIP
- **Retrieval**: `retrieve(query, k=5)` returns rank, chunk_id, document, page, text, similarity
- **Generation**: LLM ONLY uses retrieved context, cites [Doc, p. X], says "Insufficient information..." if insufficient, no invented citations. Provider abstraction: openai, groq, openrouter, together, ollama, mock (extractive fallback).

## 5. Experimental Design

- **Independent variable**: K ∈ {1,3,5,10}
- **Dependent variables**: accuracy, relevance, hallucination, response time
- **Design**: Paired — same question tested at all K, question as unit.
- **Runs**: 50 × 4 = 200 (pilot 5×4=20)
- **Constants**: docs, preprocessing, chunks, embedding, vector DB, metric, questions, ground truth, LLM, prompt, gen params, eval method.

## 6. Evaluation Metrics

### Answer Accuracy
0-2 scale: 0=incorrect/missing, 1=partially correct, 2=correct & complete. Normalized: sum/(2×N). Rule-based checks required_facts coverage; optional LLM judge with strict JSON schema (question, ground_truth, answer).

### Context Relevance
0-3 per chunk: 0=irrelevant, 1=weakly related, 2=useful, 3=directly useful. Aggregate: sum/(3×K). Distinguishes vector similarity from human/LLM judged relevance.

### Hallucination Rate
Claim-level: extract claims → compare vs retrieved evidence → label SUPPORTED/UNSUPPORTED/CONTRADICTED. Rate = (UNSUPPORTED+CONTRADICTED)/TOTAL. "Unsupported" ≠ false, just not established by context.

### Response Time
retrieval_time_ms, generation_time_ms, total_response_time_ms via high-res timing. No fake times.

## 7. Installation

### Python 3.10+ recommended

```bash
git clone <repo>
cd ContextLens
pip install -r requirements.txt
```

For embeddings:
- torch + sentence-transformers required for MiniLM. If unavailable, TF-IDF fallback activates (384 features).

### Node 18+

```bash
cd frontend
npm install
```

## 8. Environment Variables

Copy `.env.example` to `.env`:

```
LLM_PROVIDER=mock
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
GROQ_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Provider options: openai, groq, openrouter, together, ollama, mock.

If no key, system uses mock extractive generation (first chunk snippet + citation) — clearly flagged. No silent fake answers.

## 9. Preprocessing

```bash
python -m src.preprocessing
# Output: data/processed/pages.jsonl + preprocessing_stats.json
```

## 10. Running Embeddings

```bash
python -m src.embeddings
# Or force recompute:
python -m src.embeddings --force
# Output: embeddings.npy, faiss.index, embedding_meta.json
```

## 11. Running Retrieval (test)

```bash
python -m src.retriever --query "What is eligibility for M.Tech?" --k 5
```

## 12. Benchmark Generation / Validation

If you have official benchmark, place at `data/benchmark/ContextLens_Benchmark_50_Questions.json`.

Otherwise generate from PDFs (grounded but synthetic):

```bash
python -m src.generate_benchmark
```

Validate dataset:

```bash
python -m src.validate_dataset
# Output: data/processed/validation_report.json
```

## 13. Running Pilot (5×4=20 runs)

```bash
python -m src.experiment --pilot
# Outputs: results/pilot_runs.jsonl, pilot_results.csv, pilot_comparison_table.csv, pilot_failure_cases.json, figures/
```

Check pilot report, retrieval quality, citations, latency, errors before full run.

## 14. Running Full Experiment (50×4=200)

Requires LLM configured for real generation. If mock, still runs but answers are extractive.

```bash
# With API key set in .env
python -m src.experiment --full

# Or limit questions for testing:
python -m src.experiment --full --questions 10 --k-values 1,3,5,10
```

Outputs:

```
results/raw_runs.jsonl
results/results.csv
results/comparison_table.csv
results/question_level_results.csv
results/failure_cases.json
results/statistical_analysis.csv
results/figures/
  accuracy_vs_k.png
  relevance_vs_k.png
  hallucination_vs_k.png
  response_time_vs_k.png
  accuracy_distribution_by_k.png
  hallucination_distribution_by_k.png
  response_time_distribution_by_k.png
  question_level_k_comparison.png
  retrieval_similarity_distribution.png
  failure_case_summary.png
```

## 15. Starting Backend (FastAPI)

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
# Or:
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

Health: GET http://localhost:8000/health
Query: POST http://localhost:8000/api/query {"question":"...","k":5}
Experiment: POST http://localhost:8000/api/experiment {"question":"..."}
Summary: GET http://localhost:8000/api/results/summary
Question: GET http://localhost:8000/api/results/question/{id}
Benchmark: GET http://localhost:8000/api/benchmark
Failure: GET http://localhost:8000/api/failure-cases
Figures: GET http://localhost:8000/figures/{filename}
```

## 16. Starting Frontend (Next.js)

```bash
cd frontend
npm run dev
# http://localhost:3000

# Build:
npm run build
npm start
```

Frontend env: `NEXT_PUBLIC_API_URL=http://localhost:8000` (default).

Pages:

- `/` Landing: hero, K cards, system status, architecture
- `/experiment` Experiment Lab: question input, benchmark examples, pipeline viz, 4 columns Top-1/3/5/10 with chunks, similarity, answer, metrics
- `/inspector` Context Inspector: rank, doc, page, similarity, text, expand/collapse, why retrieved
- `/dashboard` Research Dashboard: Accuracy/Relevance/Hallucination/Time vs K charts, summary cards, comparison table, figures (neutral language, no winner)
- `/failures` Failure Cases: auto-identified examples with explanation
- `/methodology` Methodology: dataset, chunking, embedding, vector search, K, LLM, metrics, design, interactive diagram
- `/about` About: research question, hypothesis, setup, limitations, future work, citations

UX: loading, skeleton, error, empty, API status, progress, expandable context, source badges, metric tooltips, responsive, dark lab aesthetic (black/charcoal, white typography, red accent, thin borders).

## 17. Results

Experiment not yet run — run pilot then full.

After run, check:

- `results/comparison_table.csv` for aggregated metrics by K
- `results/figures/` for publication-quality charts
- `results/failure_cases.json` for interesting cases
- `results/statistical_analysis.csv` for Wilcoxon + Holm

Do NOT claim a K is best before measuring. Conclusion must come from data.

## 18. Limitations

- 2 docs, 62 pages, domain-specific
- MiniLM lightweight; larger embeddings may differ
- Rule-based eval; human eval more reliable
- Mock fallback when no LLM key
- Fixed chunking 500/80
- 50 Qs moderate power

## 19. Future Work

- Adaptive K based on query complexity/confidence
- Compare embeddings (MPNet, E5, BGE) + re-ranking (cross-encoder)
- Context compression: summarize Top-10
- Human eval
- Multi-hop synthesis
- Cost vs quality tradeoff
- Larger K (20,50) + diverse LLMs

## 20. Project Structure

```
ContextLens/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── README.md
│   ├── raw/
│   │   ├── Information_Brochure_2026.pdf
│   │   └── PhD_IB_A2026.pdf
│   ├── processed/
│   │   ├── pages.jsonl
│   │   ├── chunks.jsonl
│   │   ├── embeddings.npy
│   │   ├── faiss.index
│   │   └── ...
│   └── benchmark/
│       ├── ContextLens_Benchmark_50_Questions.json
│       └── ContextLens_Benchmark_50_Questions.csv
├── src/
│   ├── config.py
│   ├── utils.py
│   ├── preprocessing.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── retriever.py
│   ├── generator.py
│   ├── evaluation.py
│   ├── experiment.py
│   ├── validate_dataset.py
│   └── generate_benchmark.py
├── notebooks/
│   └── experiment.ipynb
├── results/
│   ├── raw_runs.jsonl
│   ├── results.csv
│   ├── comparison_table.csv
│   ├── question_level_results.csv
│   ├── failure_cases.json
│   └── figures/
├── backend/
│   └── app/
│       ├── main.py
│       ├── schemas.py
│       ├── config.py
│       └── services/
│           ├── rag_service.py
│           ├── experiment_service.py
│           └── evaluation_service.py
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── app/
│       │   ├── page.tsx (Landing)
│       │   ├── experiment/page.tsx
│       │   ├── inspector/page.tsx
│       │   ├── dashboard/page.tsx
│       │   ├── failures/page.tsx
│       │   ├── methodology/page.tsx
│       │   └── about/page.tsx
│       ├── components/
│       │   ├── Navbar.tsx
│       │   ├── MetricCard.tsx
│       │   └── PipelineViz.tsx
│       └── lib/
│           └── utils.ts
└── presentation/
    └── outline.md
```

## 21. Reproducibility

- Python 3.10+, Node 18+
- Embedding: all-MiniLM-L6-v2 (384d) or TF-IDF fallback
- Chunk: 500 words, 80 overlap, para-aware
- Retrieval: cosine (FAISS IP), K=1,3,5,10
- LLM: configurable provider, temperature 0.1, max_tokens 512, system prompt fixed
- Eval: rule-based by default, optional LLM judge via EVAL_USE_LLM_JUDGE=true
- Same chunks for all K
- Paired statistical tests

## 22. References

- Lewis et al. (2020). RAG. NeurIPS.
- Reimers & Gurevych (2019). Sentence-BERT. EMNLP.
- Johnson et al. (2019). FAISS. IEEE Big Data.
- Es et al. (2024). RAGAS.
- IIT Roorkee official brochures (primary data).

---

**Backend:** http://localhost:8000  
**Frontend:** http://localhost:3000  
**Run full pipeline:** see sections 9-16.

If LLM unavailable: `LLM generation unavailable. Configure LLM_PROVIDER/LLM_MODEL/API key.` — everything else works.

