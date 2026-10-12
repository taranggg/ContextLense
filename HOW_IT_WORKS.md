# How ContextLens works

This is a walkthrough of the whole project for anyone who didn't write the code: what it
does, how the pieces fit together, how RAG works here specifically, how the local LLM runs,
and exactly which file does what. Read it top to bottom once, then use it as a map.

---

## 1. What the app actually does

You upload a PDF. The app reads it, breaks it into small overlapping passages, and turns each
passage into a vector (a list of numbers that represents its meaning). When you ask a question,
it turns your question into a vector too, finds the passages whose vectors are closest to it,
hands those passages to a language model running **on your Mac** (no internet, no API key), and
asks it to answer *using only those passages* and to say exactly which passage backs each
sentence.

That whole pattern — retrieve relevant text, then generate an answer grounded in it — is called
**RAG: Retrieval-Augmented Generation**. It's the core idea of this whole app.

There's a second mode, **Research**, which exists to answer one specific question: *if you give
the model more passages (K=1 vs K=3 vs K=5 vs K=10), does the answer actually get better?* It
runs the same question through the same pipeline at different depths so you can compare.

---

## 2. The big picture (one diagram)

```text
┌─────────────────────────────┐        ┌──────────────────────────────────────────────┐
│   Browser (frontend/)        │  HTTP  │   Backend API (backend/app/)                  │
│   React + TypeScript + Vite  │◄──────►│   FastAPI, runs on http://127.0.0.1:8000      │
│   runs on :5173               │        │                                                │
└─────────────────────────────┘        └──────────────────────────────────────────────┘
                                                        │
                      ┌─────────────────────────────────┼─────────────────────────────────┐
                      ▼                                 ▼                                 ▼
          ┌───────────────────────┐        ┌───────────────────────┐        ┌───────────────────────┐
          │  Upload a PDF          │        │  Ask a question         │        │  Research: compare K  │
          │  extract → chunk        │        │  embed → retrieve         │        │  same Q at K=1,3,5,10 │
          │  → embed → index        │        │  → generate → cite        │        │                        │
          └───────────────────────┘        └───────────────────────┘        └───────────────────────┘
                      │                                 │
                      ▼                                 ▼
          data/documents/<id>/              local files on disk + the
          (PDF, text, chunks,               local language model
           vectors, FAISS index)            (MLX, Apple Silicon only)
```

Nothing here calls an external AI API. The embedding model and the language model both run as
processes inside the backend, loaded from files cached on your machine.

---

## 3. The RAG pipeline, step by step

This is the heart of the project. Every uploaded PDF goes through this exact sequence, run by
`backend/app/services/document_service.py` (look at the method `_process`, which calls each
step below in order).

### Step 1 — Extract text from the PDF

**File:** `backend/app/services/preprocessing_service.py`

We use a library called **PyMuPDF** (imported as `pymupdf`/`fitz`) to open the PDF and pull out
the text, one page at a time. For each page we get a list of text blocks (roughly, paragraphs),
clean them up (fix hyphenated line breaks, strip page numbers and repeated
headers/footers), and end up with one `PageRecord` per page:

```python
PageRecord(document_id=..., document_name=..., page=3, text="...", paragraphs=[...], word_count=412, has_text=True)
```

If a page has almost no text (for example, a scanned image with no selectable text layer),
`has_text=False`. If **every** page is like that, the whole document is marked `failed` with a
clear "this looks scanned, OCR isn't implemented" message — the app never pretends to have read
something it couldn't.

### Step 2 — Split into overlapping passages ("chunking")

**File:** `backend/app/services/chunking_service.py`

A whole PDF page is too big to search well, and a single sentence is too small to answer a
question from. So we break the document into **passages of about 500 words, with 80 words of
overlap between consecutive passages**. The overlap matters: if an important sentence happens to
fall right on the boundary between two passages, the overlap means it still shows up whole in at
least one of them.

Chunking respects paragraph boundaries (it won't cut a sentence in half if it can help it), and a
passage can span two adjacent pages if a paragraph crosses a page break — in that case we record
*every* page it touches, so citations are never wrong about which page something is on.

Every passage gets a **stable ID** (`make_chunk_id`) so the same input always produces the same
IDs — useful for caching and for the tests.

### Step 3 — Turn each passage into a vector ("embedding")

**File:** `backend/app/services/embedding_service.py`

We use a small, local model called **`sentence-transformers/all-MiniLM-L6-v2`**. Give it a
string of text, it gives you back a list of 384 numbers (a "vector" or "embedding"). The key
property: **passages with similar meaning end up with similar vectors**, even if they use
different words. This is what makes "search by meaning" possible instead of just keyword search.

We normalize every vector to length 1 (`normalize_embeddings=True`). That's not an accident — it
makes the next step's math work out to **cosine similarity**, which is explained below.

### Step 4 — Build a search index

**File:** `backend/app/services/retrieval_service.py`

All the passage vectors for one document go into a **FAISS index**
(`faiss.IndexFlatIP` — "IP" = inner product). FAISS is a library for fast vector search. Because
our vectors are all normalized to length 1, the inner product between any two of them is
mathematically identical to the **cosine similarity** between them — a number from -1 to 1 that
says how close in meaning two pieces of text are (closer to 1 = more similar).

Each document gets its **own** index, stored at `data/documents/<document-id>/index.faiss`. That
file-per-document design is what guarantees a deleted or unselected document can never leak into
another document's search results.

### Step 5 — Retrieve: find the best passages for a question

Still in `retrieval_service.py`, method `retrieve(query, document_ids, k)`:

1. Embed the question with the same MiniLM model (step 3).
2. Search each selected document's FAISS index for the `k` closest vectors.
3. Merge the results from all selected documents by score and keep the top `k` overall.

This returns a ranked list of passages, each labeled `S1`, `S2`, `S3`... (`rank` 1 = most
similar) along with its similarity score, document name, and page numbers.

**Important nuance:** a high similarity score means "this text is topically close to the
question," not "this text proves the answer is correct." The app is careful never to conflate
the two — the UI always labels it "similarity," never "confidence" or "relevance."

### Step 6 — Build the prompt and ask the LLM

**File:** `backend/app/services/rag_service.py` (orchestration) and
`backend/app/services/prompts.py` (the actual instructions given to the model)

The retrieved passages get formatted into a prompt that looks roughly like this:

```text
Sources:

[S1] brochure.pdf, page 4
<text of the passage>

[S2] brochure.pdf, pages 6–7
<text of the passage>

Question: What is the minimum CGPA for M.Tech admission?
```

The **system prompt** (the instructions the model always gets, regardless of the question) tells
it, among other things:

- Answer *only* from the sources given — no outside knowledge.
- If the sources don't have the answer, say so explicitly (a fixed sentence the app can detect:
  see `ABSTAIN_SENTENCE` in `prompts.py`).
- Cite the source marker (`[S1]`, `[S2]`, ...) for every factual claim.
- Never invent a source that wasn't given.

The exact wording of this prompt is a big deal for an experiment like this — change it and you
change the results — so it's versioned (`PROMPT_VERSION` in `prompts.py`) and every saved
research run records which version produced it.

### Step 7 — Turn the model's citations into real, clickable citations

**File:** `backend/app/services/rag_service.py` — `build_citations()`

The model's raw answer is just text with `[S1]`-style markers sprinkled in. This function:

1. Finds every `[S#]` marker in the answer.
2. Looks up what `S#` actually refers to (which passage, which document, which pages).
3. Finds the *specific sentence or two inside that passage* that best matches what the model
   said near that marker (`best_excerpt()`), so the UI can show a short, relevant excerpt instead
   of the whole 500-word passage.
4. If the model cites a marker that was never given to it (hallucinated a source), that marker is
   flagged as **invalid** and is never shown to you as if it were real.

This is the mechanism that makes citations trustworthy: they're not the model's free-form claim
about where it got something, they're the app's own lookup into data it retrieved itself.

### The whole RAG request, start to finish

```text
your question
   │
   ▼
embed the question (MiniLM)                         [embedding_service.py]
   │
   ▼
search FAISS index(es) of selected documents → top-K passages   [retrieval_service.py]
   │
   ▼
build a prompt: system instructions + the K passages + your question   [prompts.py]
   │
   ▼
run the local LLM on that prompt → raw answer text    [llm_service.py]
   │
   ▼
map [S#] markers in the answer back to real passages, pick excerpts   [rag_service.py]
   │
   ▼
send back: answer text + citations + retrieved passages + timings
```

All of this is orchestrated by `RAGService.answer()` in `rag_service.py` — that's the one
function to read if you want to see the whole thing in one place.

---

## 4. How the local LLM actually runs

**File:** `backend/app/services/llm_service.py`

### What model, and why

The default model is **`mlx-community/Qwen3-4B-Instruct-2507-4bit`** — a 4-billion-parameter
instruction-tuned language model, compressed ("quantized") to 4-bit weights so it fits
comfortably in 16 GB of memory and runs fast on Apple Silicon.

### What is MLX?

**MLX** is Apple's machine-learning framework built specifically for Apple Silicon's unified
memory architecture. **`mlx-lm`** is a library built on top of it for running language models. We
use it instead of, say, calling OpenAI's API, because the whole point of this app is that nothing
leaves your machine.

### The adapter pattern

The code doesn't call `mlx-lm` directly from everywhere it needs a model — it goes through a
small interface called `LLMBackend` (defined at the top of `llm_service.py`), with one real
implementation, `MLXBackend`. This matters for two reasons:

1. **Testability.** The test suite (`backend/tests/conftest.py`) swaps in a `FakeLLM` that
   returns a scripted answer instantly — so running the tests never needs to download or run the
   real 2+ GB model.
2. **Extensibility.** If someone wants to add support for another local runtime (llama.cpp,
   Ollama, whatever), they implement the same four methods (`status`, `start_loading`,
   `count_tokens`, `generate`) and register it — nothing else in the app needs to change.

### Loading the model (once, not per-question)

Loading a language model from disk into memory takes a couple of seconds. We do this **once**,
in the background, right when the backend server starts (`start_loading()`, called from
`main.py`'s startup code), and keep it resident in memory. Every question after that reuses the
already-loaded model — only the first request would otherwise pay the load cost.

`/api/ready` reports the model's status at any moment: `not_loaded` → `loading` → `ready`
(or `not_downloaded` / `unavailable` / `error` if something's wrong) — that status is what
powers the little colored dot in the app's header.

### Generating an answer

```python
GenerationParams(max_tokens=384, temperature=0, top_p=1.0)
```

- **`temperature=0`** means "always pick the most likely next word" — deterministic, not
  creative. For a system that's supposed to answer *only* from given facts, we don't want the
  model improvising.
- **`max_tokens=384`** caps how long an answer can be (a safety limit, not a target).
- Generation happens **token by token**, streamed back to the browser live (see §6) so you see
  the answer appear as it's written, instead of waiting for the whole thing.

### The context window budget

A language model can only "see" a limited number of tokens (word-ish pieces) at once — here,
**12,288 tokens total**, prompt + answer. Asking for 10 passages at once can produce a prompt
that's too big to fit. `RAGService._fit_context()` in `rag_service.py` handles this: it counts
tokens, and if the prompt is too big, it trims from the **lowest-ranked** (least similar) passage
first, shortening or dropping it, until everything fits. The response tells you if this happened
(`context_truncated`).

### Why MLX-only

MLX only runs on Apple Silicon. On any other machine, `MLXBackend` detects this at startup and
reports itself as `unavailable` with a clear message — the rest of the app (upload, search,
browse passages) still works, you just can't generate answers. This is intentional: **the app
never fakes a language-model answer**. If the model can't run, you get an honest error, not a
templated or canned response.

---

## 5. Feature-by-feature map

### Upload & process a PDF

| What | Where |
|---|---|
| Frontend upload UI (drag-drop, per-file progress, up to 5 files) | `frontend/src/components/Uploader.tsx` |
| API endpoints: single upload, batch upload, list, get, delete, reprocess | `backend/app/api/documents.py` |
| PDF validity checks (extension, MIME type, header, opens in PyMuPDF, not encrypted) | `backend/app/services/preprocessing_service.py` → `validate_pdf_upload`, `inspect_pdf` |
| The extract → chunk → embed → index pipeline | `backend/app/services/document_service.py` → `_process` |
| Where processed documents live on disk | `backend/app/storage/document_files.py` |
| Document status/metadata (survives a restart) | `backend/app/storage/metadata_store.py` (PostgreSQL, via `docker-compose.yml`) |

### Chat with a document

| What | Where |
|---|---|
| Chat UI: message list, input box, stop button, sources list | `frontend/src/pages/Workspace.tsx`, `frontend/src/components/Turn.tsx` |
| Rendering the model's markdown-ish answer + clickable `[S#]` citations | `frontend/src/components/AnswerText.tsx` |
| "Source inspector" side panel (every retrieved passage, similarity, raw passages) | `frontend/src/components/Inspector.tsx` |
| Non-streaming chat endpoint | `backend/app/api/chat.py` → `POST /api/chat` |
| Streaming chat endpoint (what the UI actually uses) | `backend/app/api/chat.py` → `POST /api/chat/stream`, via `backend/app/api/sse.py` |
| The RAG logic itself | `backend/app/services/rag_service.py` |
| Retrieval (the vector search) | `backend/app/services/retrieval_service.py` |
| The system prompt the model is given | `backend/app/services/prompts.py` |

### Research mode (compare K=1 vs 3 vs 5 vs 10)

| What | Where |
|---|---|
| Research UI: run a live comparison, view saved comparisons, view benchmark charts | `frontend/src/pages/Research.tsx` |
| Bar charts | `frontend/src/components/BarChart.tsx` |
| Live comparison endpoint | `backend/app/api/research.py` → `POST /api/research/compare` |
| The "run it at every K with identical settings" logic | `backend/app/services/experiment_service.py` |
| Automatic (non-LLM) scoring: did the answer contain the required facts? are claims backed by the passages? | `backend/app/services/evaluation_service.py` |
| The offline 50-question benchmark command-line tool | `backend/app/research/benchmark.py` |
| The 50 questions + their expected answers | `data/benchmark/ContextLens_Benchmark_50_Questions.json` |
| Results of benchmark runs | `results/benchmark/<run-id>/` |

### Cross-cutting / plumbing

| What | Where |
|---|---|
| All settings (`.env` values, defaults) | `backend/app/config.py` |
| Request/response shapes (Pydantic models) shared by the whole backend | `backend/app/schemas.py` |
| Wires every service together once at startup | `backend/app/container.py` |
| FastAPI app, CORS, startup/shutdown | `backend/app/main.py` |
| Turns internal errors into clean `{"error": {"code", "message"}}` JSON | `backend/app/api/errors.py` |
| The typed API client the frontend uses to talk to the backend | `frontend/src/api/client.ts`, `frontend/src/api/types.ts` |
| Polling hooks (document list, model readiness) | `frontend/src/lib/hooks.ts` |

---

## 6. A few mechanisms worth understanding on their own

### Streaming (why the answer appears word by word)

Generating an answer can take many seconds (longer with more passages). Instead of making you
stare at a spinner, the backend streams it using **Server-Sent Events (SSE)** — a simple
one-way "the server pushes, the browser listens" connection. See `backend/app/api/sse.py` for the
plumbing and `backend/app/api/chat.py`'s `/api/chat/stream` for how it's used: it emits a
`retrieval` event (here are the passages), then a `token` event per word/piece as the model
generates it, then a final `done` event with the complete, structured answer. Closing the
connection (clicking "stop") cancels generation immediately.

### Why documents don't leak into each other's answers

Every document has its own folder (`data/documents/<id>/`) and its own FAISS index file. When
you ask a question against documents A and B, the code searches *only* A's index and *only* B's
index — it's structurally impossible for an unselected or deleted document's text to show up,
because its index is never opened.

### Why citations can be trusted (or at least, are never fabricated-looking)

As covered in step 7 above: every citation shown in the UI was constructed by the backend from
data it actually retrieved, not transcribed from whatever the model claimed. If the model
invents a citation number that doesn't correspond to anything it was given, that gets filtered
out before it ever reaches you — you'll never see a "citation" to nothing in the UI.

### Why research mode is actually a fair comparison

For the K-comparison to mean anything, **everything except K must stay identical**: same model,
same prompt, same temperature, same chunking, same embedding model. `experiment_service.py`
builds one `ExperimentSettings` snapshot per run and reuses it for every condition, and this
snapshot is saved alongside the results — so you can always check afterward that nothing but K
actually changed.

---

## 7. Everyday commands

```bash
# backend (from the repo root, with the virtualenv active)
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# frontend (from frontend/)
pnpm dev

# backend tests (fast — no model download, uses FakeLLM/FakeEmbedder)
python -m pytest

# the offline research benchmark
python -m backend.app.research.benchmark ingest     # index the sample PDFs once
python -m backend.app.research.benchmark run         # run all 50 questions × all conditions
```

See `README.md` for full setup instructions, configuration options, and troubleshooting.
