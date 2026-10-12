# ContextLens

Upload a PDF, ask questions about it, and get answers grounded in cited passages from the
original document. Retrieval, embeddings and generation all run locally. No hosted AI API is
used, and no API key is needed.

ContextLens has two modes:

- **Documents (product mode).** Upload a PDF and chat with it. Each answer cites the passages
  it used, and you can open every passage in a source inspector.
- **Research mode.** Ask the same question at retrieval depths K = 1, 3, 5 and 10, compare the
  answers side by side, and read the results of the offline 50-question benchmark.

The research question behind the project is: *how does retrieval depth affect the quality of
answers that a local LLM produces with RAG?*

## Architecture

```text
React + TypeScript + Vite (frontend/)
        │  REST + server-sent events
FastAPI (backend/app)
        ├─ document_service      upload → validate → extract → chunk → embed → index (background worker)
        ├─ preprocessing_service PyMuPDF page-by-page text extraction, artifact cleaning, no OCR
        ├─ chunking_service      paragraph-aware ~500-word chunks, 80-word overlap, page-tracked
        ├─ embedding_service     sentence-transformers/all-MiniLM-L6-v2 (L2-normalised)
        ├─ retrieval_service     one exact FAISS IndexFlatIP per document (scores = cosine similarity)
        ├─ llm_service           LLMBackend adapter → MLXBackend (mlx-lm, Apple Silicon)
        ├─ rag_service           context budgeting, [S#] source labels, citation mapping, excerpts
        ├─ experiment_service    K comparisons with an identical settings snapshot, persisted
        └─ research/benchmark.py offline benchmark: no-RAG, K=1/3/5/10, gold page
storage: SQLite metadata + per-document folders under data/ (see data/README.md)
```

**How citations work.** Each retrieved passage is shown to the model as `[S1]`, `[S2]`, and so
on, together with its document name and pages. The model is told to cite only those markers.
The backend then maps each marker back to the stored chunk metadata (document, pages,
similarity) and selects the best-matching excerpt. A marker that does not correspond to a
supplied passage is reported as invalid and is never displayed as a citation. A citation only
shows where a statement came from; it does not prove the statement is correct, so the full
passage is always available to inspect.

## Requirements

- macOS on Apple Silicon (tested on an M4 with 16 GB) for local generation. On other machines
  everything except generation still works, and the app reports the model as *unavailable*.
- Python 3.12 (3.11+ should work). Verified with 3.12.11.
- Node 20+ and pnpm or npm. Verified with Node 24.4 and pnpm 11.9.
- About 3 GB of disk space for the model, plus about 100 MB for the embedding model.

## Setup

All commands run from the repository root unless noted.

### 1. Backend

```bash
python3.12 -m venv .venv          # or: uv venv --python 3.12
source .venv/bin/activate
pip install -r requirements.txt   # or: uv pip install -r requirements.txt
cp .env.example .env              # defaults work as-is
```

### 2. Local model (one-time download, ~2.3 GB)

```bash
hf download mlx-community/Qwen3-4B-Instruct-2507-4bit
```

By default the backend never downloads models at runtime (`LLM_ALLOW_DOWNLOAD=false`). If the
model is missing, `/api/ready` and the header status show *Model not downloaded* together with
the command above, and questions return HTTP 503. No substitute answer is generated.

To use a different checkpoint, set `LLM_MODEL` to any MLX-LM-compatible Hugging Face repo or
local path. Instruct models in the 3–4B range fit comfortably in 16 GB. The default is a
non-thinking instruct model, so it does not emit reasoning tokens. The embedding model downloads
automatically on first use and is cached by Hugging Face.

### 3. Frontend

```bash
cd frontend
pnpm install                      # or: npm install
cp .env.example .env              # VITE_API_BASE_URL=http://localhost:8000
```

## Run

```bash
# terminal 1 — API on http://127.0.0.1:8000 (docs at /docs)
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# terminal 2 — UI on http://localhost:5173
cd frontend && pnpm dev
```

The model loads in the background at startup (about 2 s once it is cached). The status button
in the header shows the model, embedding and storage state.

> If another process is already listening on port 8000 (for example an older ContextLens
> server), stop it first. Otherwise the browser may reach the wrong server.

Production build of the UI: `cd frontend && pnpm build` (output goes to `frontend/dist`).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness only. Says nothing about the model. |
| GET | `/api/ready` | Separate status for backend, storage, embedding model and LLM (`ready`, `loading`, `not_downloaded`, `unavailable`, …) |
| POST | `/api/documents` | Multipart upload (`file`). Returns `202` with the document; poll it for status. |
| GET | `/api/documents` | List documents with status, pages, chunks and warnings |
| GET | `/api/documents/{id}` | One document |
| DELETE | `/api/documents/{id}` | Delete the PDF, extracted text, chunks, vectors, index and related comparisons |
| POST | `/api/documents/{id}/reprocess` | Retry a failed or interrupted document |
| GET | `/api/documents/{id}/chunks?offset=&limit=` | Inspect indexed passages |
| POST | `/api/chat` | `{question, document_ids, k?}` → answer, citations, retrieved chunks, latency, model info |
| POST | `/api/chat/stream` | Same as `/api/chat`, as SSE (`retrieval`, `token`…, `done` or `error`). Closing the connection stops generation. |
| POST | `/api/research/compare` (+ `/stream`) | Runs the same question at K = 1, 3, 5, 10 (optionally with a no-RAG baseline) and saves the result |
| GET | `/api/research/results` | Saved comparisons and benchmark run summaries |
| GET | `/api/research/comparisons/{id}`, `/api/research/benchmark/{run_id}` | Full records |

Errors always have the form `{"error": {"code", "message"}}`. Stack traces and filesystem paths
are never returned. Status codes:

- 413: file too large
- 415: not a PDF
- 400: unreadable, encrypted or invalid PDF
- 409: document missing or not ready
- 503: local model unavailable
- 502: generation failed

## Documents: behaviour and limits

- **Upload checks:** PDF only, 25 MB maximum (`MAX_UPLOAD_MB`). The extension, declared MIME
  type and `%PDF-` header are all checked, and the file must open in PyMuPDF.
  Password-protected PDFs are rejected.
- **No OCR.** A PDF with no text layer fails with an explicit "OCR is not implemented" message.
  Pages without text inside an otherwise normal PDF are listed as a warning and are not
  searchable.
- **Page numbers** are physical page positions (1-based), the same as a PDF viewer's page
  counter, not printed page labels. Chunks can span adjacent pages; each citation shows the
  page(s) its excerpt comes from and the full span of the passage.
- **Document scope:** only the documents you select are searched. Every document has its own
  index, so unselected or deleted documents cannot appear in results.
- **Persistence:** after a restart, documents and their indexes are still available. Documents
  that were mid-processing are marked *interrupted* and can be retried.
- **One question at a time:** each question is answered on its own from retrieved passages.
  Earlier turns are not sent to the model, so follow-up questions should be self-contained.
- **Context budget:** the default budget is 12,288 tokens (prompt plus answer). Top-10 with
  500-word passages uses about 8–9k tokens. If a prompt would exceed the budget, the
  lowest-ranked passages are trimmed and the response reports `context_truncated`.

## Research and evaluation

```bash
python -m backend.app.research.benchmark ingest     # index data/raw/*.pdf as "Sample" documents
python -m backend.app.research.benchmark validate   # check benchmark page references → data/benchmark/validation_report.json
python -m backend.app.research.benchmark run        # 50 questions × conditions → results/benchmark/<run-id>/
python -m backend.app.research.benchmark run --questions 5 --run-id pilot   # quick pilot
python -m backend.app.research.benchmark rescore --run-id <id>              # recompute metrics from stored answers
```

**Conditions.** Every condition uses the same model checkpoint, generation parameters (temperature
0, 384 max tokens), RAG prompt (`rag-v1`), embedding model, chunks and index. Only the evidence
given to the model changes:

| Condition | Evidence |
| --- | --- |
| `no_rag` | None. Uses a context-free prompt (unavoidably different) with the same model and parameters. |
| `k1`, `k3`, `k5`, `k10` | Top-K retrieved passages across both sample PDFs |
| `gold` | The benchmark's cited page. Only for questions whose citation passed validation. |

Runs are interleaved per question and written incrementally, so an interrupted run can be resumed
with the same `--run-id`.

**Metrics.** All metrics are rule-based and lexical, and none of them has been validated against
human judgement:

| Metric | Definition |
| --- | --- |
| Answer accuracy | The original ContextLens 0/1/2 rubric. Scores 2 if at least 80% of the required facts appear in the answer and 1 if at least 40% do. A fact counts as present when at least 60% of its content words and all of its numbers appear. Abstentions score 0. Reported normalised (÷2). |
| Context fact recall | Share of required facts found in the supplied passages |
| Fact-bearing precision | Share of supplied passages containing at least one required fact |
| Gold page retrieved | Whether any supplied passage includes the validated gold page |
| Lexical claim support | An answer sentence counts as *supported* if at least 60% of its content words and all of its numbers occur in the supplied context. *Unsupported* means not established by that evidence, not false. Contradictions are **not** detected. |
| Citation validity | Share of `[S#]` markers that match a supplied passage. Also tracks whether the answer cites the gold page. |
| Latency | Retrieval, generation and total time, measured on the machine that ran the benchmark |

`summary.json` also reports paired Wilcoxon signed-rank tests between conditions on the per-question
rubric scores and total latency, Holm-corrected within each metric.

No LLM judge is used. The generator should not grade itself, and no second local judge model has
been validated. In live comparisons for uploaded documents there is no ground truth, so
correctness is shown as **Not evaluated**.

**About the benchmark.** The 50 questions were generated from the sample PDFs, and their cited
pages came from a keyword search. The automatic validation found the required facts on the cited
page for 25 questions, on a different page for 18, and nowhere in the text for 7. The benchmark
file has not been edited. The gold condition covers the 25 validated questions only, and the UI
can show results restricted to that subset.

**Legacy results.** The files in `results/legacy_mock_runs/` came from an earlier mock generator
that pasted retrieved text instead of calling an LLM. They are kept for provenance only and are
not findings.

## Tests

```bash
source .venv/bin/activate
python -m pytest                 # 60 backend tests; uses fakes, no model download needed
cd frontend && pnpm typecheck && pnpm build
```

The tests cover:

- PDF validation: extension, MIME type, header, corrupt and encrypted files, size limit, image-only PDFs
- page metadata
- chunk size, overlap, empty pages and stable unique IDs
- index and metadata alignment, document filtering, fewer than K chunks, empty and misaligned indexes
- citation mapping and invalid markers
- deletion cleanup and persistence across restarts
- API validation and SSE event order
- identical settings across K
- a missing or disabled model returning 503 instead of an answer

## Configuration

See `.env.example`. The key settings are `LLM_MODEL`, `LLM_RUNTIME` (`mlx` or `none`),
`LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_CONTEXT_TOKENS`, `EMBEDDING_MODEL`, `CHUNK_SIZE_WORDS`,
`CHUNK_OVERLAP_WORDS`, `MAX_UPLOAD_MB` and `FRONTEND_ORIGIN` (the CORS allow-list). Only
`VITE_API_BASE_URL` is exposed to the browser.

**Adding another local runtime.** Implement the `LLMBackend` protocol in
`backend/app/services/llm_service.py` (`status`, `start_loading`, `count_tokens`, `generate`) and
register it in `create_llm_backend`.

**Changing the embedding model.** Existing documents keep their original vectors. Retrieval
refuses to mix models and asks you to reprocess those documents.

## Privacy

Uploaded PDFs, extracted text, vectors and saved comparisons stay in `data/` on this machine.
Questions and document text are not sent to any hosted AI service, and the server does not log
question text. Hugging Face is contacted only to download models that are not yet cached. Data is
not encrypted at rest. Conversation history is kept only in the browser's `localStorage`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Header shows *Model not downloaded* | `hf download <LLM_MODEL>`, then restart the backend (or set `LLM_ALLOW_DOWNLOAD=true`) |
| *Model unavailable* | MLX needs macOS on Apple Silicon and `pip install mlx-lm`. Everything else still works. |
| Upload fails with "no extractable text" | The PDF is scanned or image-only. Run it through OCR (for example `ocrmypdf in.pdf out.pdf`) and upload the result. |
| "indexed with a different embedding model" | Use *Retry* (reprocess) on the document after changing `EMBEDDING_MODEL` |
| Browser shows "Can't reach the ContextLens backend" | Check the backend is running and `VITE_API_BASE_URL` / `FRONTEND_ORIGIN` match the ports you use |
| Top-10 answers are slow | Expected. On an M4, prompt processing runs at about 290 tokens/s, so ~8k-token prompts take about 30 s before the first token. |
| Answer ends abruptly | It reached `LLM_MAX_TOKENS`; the inspector reports *token limit reached* |

## Project structure

```text
backend/app/        FastAPI app: api/, services/, storage/, research/benchmark.py
backend/tests/      pytest suite (fakes for embedder and LLM)
frontend/src/       pages/ (Home, Workspace, Research), components/, api/, lib/, styles/
data/               sample PDFs, benchmark, user documents (see data/README.md)
results/benchmark/  benchmark runs: config.json, runs.jsonl, summary.json
results/legacy_mock_runs/   earlier mock outputs — not results
presentation/       slide outline
```

## References

- Lewis et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.
- Reimers & Gurevych (2019). Sentence-BERT. EMNLP.
- Johnson, Douze & Jégou (2019). Billion-scale similarity search with GPUs (FAISS). IEEE Trans. Big Data.
- Es et al. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. EACL demos.
