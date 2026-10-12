# ContextLens

Upload PDFs (up to 5 at a time), ask questions about them, and get answers with citations that
point to the exact passages and pages they came from. Everything runs on your own machine. The PDF text, the
search index and the language model all stay local, and no API key or paid AI service is needed.

ContextLens has two modes:

- **Documents.** Upload one or more PDFs (up to 5 per upload) and chat with them. Each answer includes numbered citations you can
  click to read the supporting excerpt.
- **Research.** Ask one question with 1, 3, 5 or 10 retrieved passages and compare the answers
  side by side. This mode also shows the results of an offline 50-question benchmark.

The research question behind the project: *how does retrieval depth (K) affect the quality of
answers that a local LLM produces with RAG?*

---

## Contents

1. [Quick start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Step-by-step setup](#step-by-step-setup)
4. [Running the app (backend + frontend)](#running-the-app-backend--frontend)
5. [Using the app](#using-the-app)
6. [Running the research benchmark](#running-the-research-benchmark)
7. [Running the tests](#running-the-tests)
8. [How it works](#how-it-works)
9. [Configuration](#configuration)
10. [API reference](#api-reference)
11. [Limitations](#limitations)
12. [Troubleshooting](#troubleshooting)
13. [Project structure](#project-structure)

---

## Quick start

If you already have Python 3.12, Node 20+, pnpm and an Apple Silicon Mac, run these commands from
the repository root:

```bash
# one-time setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
hf download mlx-community/Qwen3-4B-Instruct-2507-4bit
(cd frontend && pnpm install)

# every time — two terminals
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000   # terminal 1: backend
cd frontend && pnpm dev                                       # terminal 2: frontend
```

Then open **<http://localhost:5173>**.

---

## Prerequisites

| Requirement | Version / notes |
| --- | --- |
| macOS on Apple Silicon (M1–M4) | Needed for local answer generation (MLX). Tested on an M4 with 16 GB RAM. On other machines upload, search and the UI still work, and the app reports the model as *unavailable*. |
| Python | 3.12 recommended (verified with 3.12.11); 3.11 should also work |
| Node.js | 20 or newer (verified with 24.4) |
| pnpm | Required for the frontend (verified with 11.9). Install with `corepack enable` or `npm install -g pnpm`. `npm install` is deliberately blocked so that `pnpm-lock.yaml` stays the single lockfile. |
| Disk space | About 3 GB: 2.3 GB for the language model and about 100 MB for the embedding model |

---

## Step-by-step setup

Do this once. All commands start from the repository root (the folder that contains this README).

### Step 1 — Create a Python environment and install the backend

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> If you use [uv](https://docs.astral.sh/uv/), `uv venv --python 3.12` and
> `uv pip install -r requirements.txt` do the same thing faster.

### Step 2 — Create the backend config file

```bash
cp .env.example .env
```

The defaults work without changes. The available settings are described in
[Configuration](#configuration).

### Step 3 — Download the local language model (about 2.3 GB, one time)

```bash
hf download mlx-community/Qwen3-4B-Instruct-2507-4bit
```

The `hf` command is installed with the backend requirements in step 1. The model is cached in
`~/.cache/huggingface`. The backend never downloads a model on its own. If this step is skipped,
the app shows **"Model not downloaded"** along with this command, and questions return an error
instead of an answer.

The embedding model (`all-MiniLM-L6-v2`, about 90 MB) downloads automatically the first time a
PDF is processed.

### Step 4 — Install the frontend

```bash
cd frontend
pnpm install
cp .env.example .env               # optional — sets VITE_API_BASE_URL=http://localhost:8000
cd ..
```

### Step 5 (optional) — Load the sample documents

```bash
python -m backend.app.research.benchmark ingest
```

This indexes the two IIT Roorkee brochures in `data/raw/`. They appear in the app labelled
**Sample**, and the research benchmark uses them. You can skip this step if you only want to use
your own PDFs.

---

## Running the app (backend + frontend)

The app has two processes, and both must be running. Use two terminal windows, both opened at the
repository root.

### Terminal 1 — Backend (FastAPI, port 8000)

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. The model then loads in the background, which takes a
few seconds the first time.

Check that it is up:

```bash
curl http://127.0.0.1:8000/api/health    # {"status":"ok",...}  — the server is running
curl http://127.0.0.1:8000/api/ready     # model, embedding and storage status
```

Interactive API docs are at <http://127.0.0.1:8000/docs>.

### Terminal 2 — Frontend (React + Vite, port 5173)

```bash
cd frontend
pnpm dev
```

Open **<http://localhost:5173>**. The status button in the top-right corner of the page should say
**Model ready**. Click it to see details for the model, embeddings and storage.

### Stopping

Press `Ctrl+C` in each terminal. Uploaded documents and their indexes are kept on disk and are
available again the next time you start the app.

### Production build of the frontend (optional)

```bash
cd frontend
pnpm build                         # output in frontend/dist
pnpm preview                       # serve the build locally
```

> **Port already in use?** If something else (for example an older ContextLens server) is on port
> 8000, stop it first: `lsof -i :8000` shows it, and `kill <PID>` stops it. Otherwise the browser
> may reach the wrong server.

---

## Using the app

1. **Upload PDFs.** On the **Documents** page, drop up to **5 PDFs** onto the upload area, or click
   *Browse files* and select several (each file can be up to 25 MB).
   - Each file gets its own status line (uploading, extracting text, splitting into passages,
     embedding, indexing, ready).
   - Invalid files, such as a non-PDF or a file that is too large, are listed with the reason.
     The other files still upload.
   - When every file is ready, the chat opens with all of them selected. If any file failed, you
     get an **Open documents** button instead.
   - Selecting more than 5 files at once shows an error and uploads nothing.
2. **Ask a question.** Type a question and press **Enter** (**Shift+Enter** adds a new line). The
   answer streams in. While it is generating, the square button stops it.
3. **Check the sources.** Numbered chips in the answer and the **Sources** list show the
   supporting excerpt, the document name and the page. Click any of them to open the
   **source inspector**. The inspector has three tabs:
   - *Retrieved passages*: every passage the model was given, with its similarity score
   - *Details*: timings, token counts and model settings
   - *All passages*: the full index for the document
4. **Search several documents.** Tick more documents in the left sidebar to search them together.
5. **Change the retrieval depth.** The *Passages per answer* selector under the input box sets
   how many passages are retrieved (1, 3, 5 or 10).
6. **Compare depths.** On the **Research** page, pick a document, enter a question and click
   **Run comparison**. The same question runs at Top-1, 3, 5 and 10, optionally with a
   no-retrieval baseline. Each comparison is saved and can be reopened later.
7. **Delete a document.** Use the trash icon on the Documents page. This removes the PDF, its
   extracted text, its passages, its vectors and any saved comparisons that used it.

How long an answer takes depends mostly on how much text the model has to read. On an M4, Top-5
takes about 15–20 s and Top-10 about 30–40 s.

---

## Running the research benchmark

The benchmark runs the 50 questions in `data/benchmark/` through the same RAG engine as the app.
Run these commands from the repository root with the virtual environment active:

```bash
# 1. index the sample PDFs (skip if already done in setup step 5)
python -m backend.app.research.benchmark ingest

# 2. check the benchmark's cited pages against the extracted text
python -m backend.app.research.benchmark validate
#    → data/benchmark/validation_report.json

# 3a. quick pilot: 5 questions
python -m backend.app.research.benchmark run --questions 5 --run-id pilot

# 3b. full run: 50 questions × 6 conditions (about 1–1.5 hours on an M4)
python -m backend.app.research.benchmark run --run-id full

# resume an interrupted run: repeat the same command with the same --run-id
# recompute metrics from saved answers without regenerating:
python -m backend.app.research.benchmark rescore --run-id full
```

Each run writes `results/benchmark/<run-id>/config.json`, `runs.jsonl` (every answer, the
retrieved passages and the scores) and `summary.json`. The **Research** page in the app shows
these results automatically, and you can open individual questions there. If no run exists, the
page says *Experiment not run*.

For the most reliable latency numbers, avoid using the app while a benchmark is running, because
both share the same GPU.

### Experimental conditions

Every condition uses the same model checkpoint, the same generation settings (temperature 0, at
most 384 output tokens), the same prompt (`rag-v1`), the same embedding model and the same chunks
and index. Only the evidence given to the model changes.

| Condition | Evidence given to the model |
| --- | --- |
| `no_rag` | None. Uses a context-free prompt (unavoidably different) with the same model and settings. |
| `k1`, `k3`, `k5`, `k10` | Top-K retrieved passages from both sample PDFs |
| `gold` | The benchmark's cited page. Only for questions whose page reference passed validation. |

### Metrics

All metrics are automatic, rule-based word-matching checks. None of them has been validated
against human judgement.

| Metric | Definition |
| --- | --- |
| Answer accuracy | The original ContextLens 0/1/2 rubric. Scores 2 if at least 80% of the required facts appear in the answer and 1 if at least 40% do. A fact counts as present when at least 60% of its words and all of its numbers appear. "Not enough evidence" answers score 0. Reported as score ÷ 2. |
| Fact recall in context | Share of required facts found in the passages given to the model |
| Fact-bearing passages | Share of the given passages that contain at least one required fact |
| Gold page retrieved | Whether any given passage includes the validated source page |
| Sentences found in context | An answer sentence counts as found if most of its words and all of its numbers occur in the given passages. "Not found" means the evidence doesn't establish it, not that it is false. Contradictions are not detected. |
| Citation validity | Share of `[S#]` markers that match a passage the model was actually given |
| Latency | Retrieval, generation and total time |

`summary.json` also includes paired Wilcoxon signed-rank tests between conditions,
Holm-corrected within each metric. No LLM-as-judge is used. For questions about your own uploads
there is no ground truth, so correctness is shown as **Not evaluated**.

### About the benchmark data

The 50 questions were generated from the sample PDFs, and their source pages were assigned by
keyword search. The automatic validation found:

- the required facts on the **cited page** for 25 questions
- the facts on a **different page** for 18 questions
- the facts **not in the extracted text at all** for 7 questions

The benchmark file has not been edited. The *Gold page* condition uses only the 25 validated
questions, and the Research page can restrict all results to that subset.

---

## Running the tests

```bash
# backend: 64 tests, using small stand-ins instead of the real models (nothing is downloaded)
source .venv/bin/activate
python -m pytest

# frontend: type-check and production build
cd frontend
pnpm typecheck
pnpm build
```

The backend tests cover:

- PDF validation: extension, MIME type, header, corrupt and password-protected files, size limit, scanned PDFs
- multi-file upload: per-file results and the 5-file limit
- page metadata
- chunk overlap and stable IDs
- index and metadata alignment, document filtering, fewer than K passages, empty indexes
- citation mapping and invalid citation markers
- deletion cleanup and persistence after a restart
- identical settings across K in research mode
- a missing model returning a clear error instead of an answer

---

## How it works

```text
Browser (React + TypeScript + Vite, port 5173)
   │  REST + streaming (server-sent events)
FastAPI backend (port 8000)
   ├─ Upload        validate PDF → save under a generated ID
   ├─ Extract       PyMuPDF, page by page, keeps page numbers (no OCR)
   ├─ Chunk         paragraph-aware, ~500 words, 80-word overlap, tracks pages
   ├─ Embed         sentence-transformers/all-MiniLM-L6-v2 (normalised vectors)
   ├─ Index         one FAISS index per document (scores = cosine similarity)
   ├─ Retrieve      Top-K passages from the selected documents only
   ├─ Generate      local LLM via MLX (Qwen3-4B-Instruct, 4-bit), loaded once
   └─ Cite          [S1], [S2]… markers mapped back to document + page + excerpt
Storage: data/contextlens.db (SQLite metadata) + data/documents/<id>/ (PDF, text, chunks, vectors)
```

**Citations.** Each retrieved passage is shown to the model as `[S1]`, `[S2]` and so on, together
with its document name and pages. The model is instructed to answer only from these passages and
to cite them. The backend maps every marker back to the stored passage, finds the best-matching
excerpt and the page it is on, and drops any marker that doesn't match a supplied passage. A
citation shows where a statement came from; it does not prove the statement is right, so the
full passage is always available to read.

**When the evidence is missing,** the model is told to say *"I couldn't find enough evidence in
the selected documents to answer this."* The app marks such answers as *Not enough evidence*.

---

## Configuration

**Backend settings** are in `.env` at the repository root (copy `.env.example`). They are read
only by the backend and are never sent to the browser.

| Setting | Default | Meaning |
| --- | --- | --- |
| `BACKEND_HOST` / `BACKEND_PORT` | `127.0.0.1` / `8000` | Where the API listens |
| `FRONTEND_ORIGIN` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins (CORS) |
| `DATA_DIR` | `./data` | Where documents, indexes and the database are stored |
| `RESULTS_DIR` | `./results` | Where benchmark runs are written |
| `MAX_UPLOAD_MB` | `25` | Size limit per PDF |
| `MAX_FILES_PER_UPLOAD` | `5` | Maximum PDFs in one upload |
| `CHUNK_SIZE_WORDS` / `CHUNK_OVERLAP_WORDS` | `500` / `80` | Passage size and overlap |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `DEFAULT_TOP_K` | `5` | Passages per answer when none is chosen |
| `RESEARCH_K_VALUES` | `1,3,5,10` | Depths compared in research mode |
| `LLM_RUNTIME` | `mlx` | `mlx`, or `none` to turn off generation |
| `LLM_MODEL` | `mlx-community/Qwen3-4B-Instruct-2507-4bit` | Any MLX-LM model ID or local path |
| `LLM_MAX_TOKENS` | `384` | Maximum answer length |
| `LLM_TEMPERATURE` / `LLM_TOP_P` | `0` / `1.0` | Sampling settings (0 means deterministic) |
| `LLM_CONTEXT_TOKENS` | `12288` | Budget for prompt plus answer. Top-10 needs about 8–9k tokens. |
| `LLM_PRELOAD` | `true` | Load the model at startup |
| `LLM_ALLOW_DOWNLOAD` | `false` | Allow the backend to download a missing model |

**Frontend setting:** `frontend/.env` holds `VITE_API_BASE_URL` (default `http://localhost:8000`).
This is the only value that reaches the browser.

**Using another model.** Download it with `hf download <id>`, set `LLM_MODEL=<id>` and restart the
backend. Instruct models of about 3–4B parameters suit a 16 GB Mac.

**Adding another local runtime.** Implement the `LLMBackend` interface in
`backend/app/services/llm_service.py` and register it in `create_llm_backend`.

**Changing the embedding model.** Existing documents keep their old vectors, and the app asks you
to re-process them; use the *Retry* button.

---

## API reference

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Server is running (says nothing about the model) |
| GET | `/api/ready` | Status of storage, embedding model and LLM |
| POST | `/api/documents` | Upload one PDF (multipart field `file`). Returns `202`; poll the document for its status. |
| POST | `/api/documents/batch` | Upload up to 5 PDFs (repeated multipart field `files`). Returns `202` with `documents` (accepted, now processing) and `errors` (rejected files, each with a reason). More than 5 files returns `400 too_many_files`. |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Document details and processing status |
| DELETE | `/api/documents/{id}` | Delete the document and all derived data |
| POST | `/api/documents/{id}/reprocess` | Retry a failed or interrupted document |
| GET | `/api/documents/{id}/chunks?offset=0&limit=20` | Browse indexed passages |
| POST | `/api/chat` | `{"question", "document_ids", "k"}` → answer, citations, passages, timings |
| POST | `/api/chat/stream` | Same as above, streamed; closing the connection stops generation |
| POST | `/api/research/compare` (and `/stream`) | Same question at K = 1, 3, 5, 10, saved |
| GET | `/api/research/results` | Saved comparisons and benchmark summaries |
| GET | `/api/research/comparisons/{id}` | One saved comparison |
| GET | `/api/research/benchmark/{run_id}` | One benchmark run, including every answer |

Errors always have the form `{"error": {"code": "...", "message": "..."}}`:

- `413` file too large
- `415` not a PDF
- `400` unreadable or encrypted PDF
- `409` document missing or not ready
- `503` local model unavailable
- `502` generation failed

---

## Limitations

- **No OCR.** Scanned or image-only PDFs are rejected with a clear message. Pages without text
  inside an otherwise normal PDF are listed as a warning and are not searchable.
- **No conversation memory.** Each question is answered on its own. Follow-up questions should
  name what they refer to.
- **Page numbers** are positions in the PDF file (what a PDF viewer's page counter shows), not
  the numbers printed on the pages.
- **The metrics are word-matching heuristics.** They can miss paraphrases and cannot detect
  contradictions, and they have not been checked against human ratings.
- **The benchmark is synthetic** and only half of its page references were confirmed (see above).
- **Generation needs Apple Silicon.** Other platforms need a new runtime adapter.
- **Storage is not encrypted.** Files are stored as plain files under `data/`.

## Privacy

Uploaded PDFs, extracted text, vectors and saved comparisons stay in `data/` on your machine.
Questions and document text are never sent to an online AI service, and the server does not log
question text. The internet is used only to download models that are not yet cached. Chat
history is kept only in your browser's local storage.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Status shows **Model not downloaded** | Run `hf download mlx-community/Qwen3-4B-Instruct-2507-4bit` (or your `LLM_MODEL`), then restart the backend |
| Status shows **Model unavailable** | MLX needs macOS on Apple Silicon and the `mlx-lm` package (`pip install mlx-lm`) |
| Page says **Can't reach the ContextLens backend** | Start the backend (terminal 1). Check that `VITE_API_BASE_URL` in `frontend/.env` matches its address. |
| Requests fail with CORS errors | Add the address you open the UI at to `FRONTEND_ORIGIN` in `.env`, then restart the backend |
| Upload fails with **no extractable text** | The PDF is scanned. OCR it first (for example `ocrmypdf in.pdf out.pdf`), then upload the result. |
| **"indexed with a different embedding model"** | You changed `EMBEDDING_MODEL`; click *Retry* on the document to re-process it |
| `Address already in use` on port 8000 | Another server is running: `lsof -i :8000`, then `kill <PID>` |
| Answers are slow | Normal for local models. The model reads about 290 tokens/s on an M4, so Top-10 (about 8k tokens) takes about 30 s before the first word. Use fewer passages for faster answers. |
| Answer stops mid-sentence | It hit `LLM_MAX_TOKENS`; the inspector's *Details* tab shows "token limit reached" |

---

## Project structure

```text
ContextLens/
├── README.md
├── requirements.txt              backend dependencies
├── .env.example                  backend settings template
├── pytest.ini
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app (entry point: backend.app.main:app)
│   │   ├── config.py             settings from .env
│   │   ├── schemas.py            request/response models
│   │   ├── container.py          wires the services together
│   │   ├── api/                  routes: health, documents, chat, research
│   │   ├── services/             preprocessing, chunking, embedding, retrieval, llm, rag, evaluation, experiments
│   │   ├── storage/              SQLite metadata store, per-document files
│   │   └── research/benchmark.py benchmark command-line tool
│   └── tests/                    pytest suite
├── frontend/
│   ├── package.json              pnpm only (packageManager: pnpm@11.9.0)
│   ├── pnpm-lock.yaml
│   ├── scripts/only-pnpm.cjs     blocks npm/yarn installs
│   ├── .env.example              VITE_API_BASE_URL
│   └── src/
│       ├── pages/                Home, Workspace (chat), Research
│       ├── components/           uploader, document list, answer, source inspector, charts
│       ├── api/                  typed API client
│       ├── lib/                  hooks and formatting
│       └── styles/global.css
├── data/                         sample PDFs, benchmark, your documents (see data/README.md)
├── results/
│   └── benchmark/<run-id>/       benchmark runs
├── docs/                         project history (original scaffolding prompt)
└── presentation/outline.md
```

## References

- Lewis et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.
- Reimers & Gurevych (2019). Sentence-BERT. EMNLP.
- Johnson, Douze & Jégou (2019). Billion-scale similarity search with GPUs (FAISS). IEEE Transactions on Big Data.
- Es et al. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. EACL (demos).
