# ContextLens — One-Shot Master Prompt for AI Code Editor

You are a senior full-stack ML engineer and research engineer.

Build the COMPLETE production-quality academic mini-project described below from scratch.

IMPORTANT:
- Do not merely generate a prototype UI.
- Do not create fake experiment results.
- Do not hardcode metrics.
- Do not skip the actual RAG pipeline.
- Do not use mock data where real data can be generated from the provided PDFs.
- The final project must be runnable locally and suitable for an M.Tech Modern AI mini-project demonstration.

---

## PROJECT

**Project Name:** ContextLens

**Project Title:** ContextLens: Investigating the Impact of Retrieval Depth on RAG Answer Quality

**Tagline:** "Does more context make AI smarter?"

### Core research question

> Does increasing the number of retrieved chunks in a Retrieval-Augmented Generation (RAG) system always improve answer quality?

Experimentally compare:

- Top-1
- Top-3
- Top-5
- Top-10

retrieved chunks.

Measure:

1. Answer Accuracy
2. Context Relevance
3. Hallucination Rate
4. Response Time

The project should demonstrate experimentally how retrieval depth K affects RAG answer quality. Do not assume in advance that more retrieved context is better.

---

## ASSIGNMENT CONTEXT

This is an M.Tech Modern AI mini-project.

The assignment specifically asks for a small RAG system using domain documents and an investigation comparing:

- Top-1 vs Top-3 vs Top-5 vs Top-10 retrieved chunks

with:

- Answer Accuracy
- Context Relevance
- Hallucination Rate
- Response Time

The project should contain:

```text
README.md
requirements.txt
data/
notebooks/
src/
results/
presentation/
```

The final presentation should be approximately 8–10 slides.

The project should be research-oriented rather than simply being a chatbot.

---

# AVAILABLE DATA

The project uses IIT Roorkee official academic documents.

Primary documents:

```text
Information_Brochure_2026.pdf
PhD_IB_A2026.pdf
```

These should be present in:

```text
data/raw/
```

There is also a benchmark containing 50 questions:

```text
ContextLens_Benchmark_50_Questions.json
ContextLens_Benchmark_50_Questions.csv
```

The benchmark consists of:

- 15 direct factual questions
- 10 procedural questions
- 10 eligibility questions
- 5 conditional questions
- 5 numerical questions
- 5 multi-part questions

Total:

```text
50 questions
```

Use the provided benchmark as the ground-truth evaluation set.

DO NOT invent new ground truth if the provided benchmark already contains the required answer.

If a benchmark item appears inconsistent with the source PDF, flag it in a validation report instead of silently changing it.

---

# EXISTING PROJECT

If a ContextLens project scaffold already exists, DO NOT unnecessarily recreate it.

Inspect the existing files first and extend/fix them.

Expected structure:

```text
ContextLens/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── README.md
│   ├── raw/
│   │   ├── Information_Brochure_2026.pdf
│   │   └── PhD_IB_A2026.pdf
│   │
│   ├── processed/
│   └── benchmark/
│
├── src/
│   ├── preprocessing.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── retriever.py
│   ├── generator.py
│   ├── evaluation.py
│   ├── experiment.py
│   ├── config.py
│   └── utils.py
│
├── notebooks/
│   └── experiment.ipynb
│
├── results/
│   ├── raw_runs.jsonl
│   ├── results.csv
│   ├── comparison_table.csv
│   ├── question_level_results.csv
│   ├── failure_cases.json
│   └── figures/
│
├── backend/
│   └── FastAPI application
│
├── frontend/
│   └── Next.js application
│
└── presentation/
    └── presentation content/documentation
```

---

# PART 1 — DOCUMENT PREPROCESSING

Implement a robust PDF preprocessing pipeline.

Requirements:

- Extract text page by page.
- Preserve document name.
- Preserve page number.
- Clean PDF artifacts.
- Remove excessive whitespace.
- Fix hyphenated line breaks where appropriate.
- Preserve paragraph boundaries where possible.
- Do not merge unrelated pages.
- Store processed pages in JSONL.

Output:

```text
data/processed/pages.jsonl
```

Each record should contain approximately:

```json
{
  "document": "...",
  "page": 1,
  "text": "...",
  "source_path": "..."
}
```

Add validation statistics:

- number of documents
- number of pages
- total extracted characters
- total words
- pages with very little text
- extraction failures

Create:

```text
src/preprocessing.py
```

It must be executable from CLI:

```bash
python -m src.preprocessing
```

---

# PART 2 — CHUNKING

Implement section-aware chunking.

Target:

```text
approximately 500 words per chunk
```

Overlap:

```text
approximately 80 words
```

Prioritize semantic/paragraph boundaries over blindly cutting at exactly 500 words.

Every chunk must retain metadata:

```json
{
  "chunk_id": "...",
  "document": "...",
  "page": 1,
  "text": "...",
  "word_count": 500
}
```

Output:

```text
data/processed/chunks.jsonl
```

CRITICAL:

The exact same chunks must be used for Top-1, Top-3, Top-5 and Top-10 experiments.

Do NOT create different chunking strategies for different K values.

This ensures that K is the experimental variable.

Create:

```text
src/chunking.py
```

---

# PART 3 — EMBEDDINGS

Implement semantic embeddings.

Default embedding model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Make the model configurable through environment/config.

Generate embeddings for every chunk.

Store them efficiently.

The system should not recompute embeddings every time the application starts.

Implement:

```text
src/embeddings.py
```

Provide CLI functionality:

```bash
python -m src.embeddings
```

Use a local vector representation such as FAISS.

---

# PART 4 — RETRIEVAL

Implement semantic retrieval using FAISS.

For every query:

1. Embed query
2. Search vector index
3. Retrieve ranked chunks
4. Return similarity scores and metadata

Support:

```text
K=1
K=3
K=5
K=10
```

Implement:

```text
src/retriever.py
```

Example interface:

```python
retrieve(query, k=5)
```

Return:

```json
[
  {
    "rank": 1,
    "chunk_id": "...",
    "document": "...",
    "page": 1,
    "text": "...",
    "similarity": 0.91
  }
]
```

The UI must eventually be able to display these retrieved chunks.

---

# PART 5 — RAG GENERATION

Implement the actual RAG generation pipeline.

The LLM must ONLY answer using retrieved context.

Prompt the model with:

- user question
- retrieved context
- source metadata

The answer should include source references such as:

```text
[Information_Brochure_2026.pdf, p. 12]
```

or:

```text
[PhD_IB_A2026.pdf, p. 8]
```

Do not allow the model to invent citations.

If the context does not contain enough information, the model should explicitly say:

```text
Insufficient information in the provided documents.
```

instead of guessing.

---

# LLM CONFIGURATION

Do NOT hardcode a single paid API provider.

Create a configurable provider abstraction.

Support at minimum:

1. OpenAI-compatible API
2. Local model option if available

Use environment variables:

```text
LLM_PROVIDER=
LLM_MODEL=
OPENAI_API_KEY=
```

Provide:

```text
.env.example
```

The application should fail gracefully if no LLM key/model is configured.

Do not expose API keys in frontend code.

---

# PART 6 — CONTROLLED EXPERIMENT

This is the MOST IMPORTANT part.

For each of the 50 benchmark questions, run:

```text
K=1
K=3
K=5
K=10
```

Therefore:

```text
50 questions × 4 retrieval depths = 200 experimental runs
```

Every run must record:

- question
- question_id
- k
- retrieved_chunks
- generated_answer
- retrieval_time
- generation_time
- total_response_time
- answer_accuracy
- context_relevance
- hallucination_rate
- source_documents
- source_pages

Output:

```text
results/raw_runs.jsonl
results/results.csv
```

---

# PART 7 — ANSWER ACCURACY

Implement a transparent evaluation method.

Each benchmark question contains ground truth / required facts.

Use a 0–2 scale:

```text
0 = incorrect / missing essential answer
1 = partially correct
2 = correct and sufficiently complete
```

Normalize:

```text
Answer Accuracy =
sum(scores) / (2 × number_of_questions)
```

Do NOT simply ask an LLM:

```text
"Is this answer good?"
```

without a defined rubric.

If an LLM judge is used, it must receive:

- question
- ground truth
- generated answer

and must follow a strict JSON schema.

Also retain the raw judgment.

---

# PART 8 — CONTEXT RELEVANCE

Measure whether retrieved chunks are actually relevant to answering the question.

Use a 0–3 scale per retrieved chunk:

```text
0 = irrelevant
1 = weakly related
2 = useful
3 = directly useful for answering the question
```

Aggregate:

```text
Context Relevance =
sum(chunk relevance scores) / (3 × K)
```

IMPORTANT:

Do not equate vector similarity with actual contextual relevance.

The experiment must distinguish:

```text
retrieval similarity
```

from:

```text
human/LLM judged relevance
```

---

# PART 9 — HALLUCINATION RATE

Implement claim-level evaluation.

For every generated answer:

1. Extract factual claims.
2. Compare each claim against retrieved evidence.
3. Label each claim:

```text
SUPPORTED
UNSUPPORTED
CONTRADICTED
```

Then calculate:

```text
Hallucination Rate =
(UNSUPPORTED + CONTRADICTED) / TOTAL CLAIMS
```

Important:

"Unsupported" means the retrieved context does not establish the claim.

It does NOT automatically mean the claim is factually false.

Store claim-level evaluation in the results.

---

# PART 10 — RESPONSE TIME

Measure separately:

```text
retrieval_time_ms
generation_time_ms
total_response_time_ms
```

Use Python high-resolution timing.

Do not use fake or estimated response times.

---

# PART 11 — PILOT EXPERIMENT

Before running all 200 experiments:

Run:

```text
5 benchmark questions × 4 K values
```

= 20 runs.

Display a clear pilot report.

Check:

- retrieval quality
- answer generation
- citations
- evaluation output
- latency
- errors

Only after successful validation should the full 200-run experiment be executed.

---

# PART 12 — MAIN EXPERIMENT

Run:

```text
50 × 4 = 200 experiments
```

Create:

```text
results/results.csv
```

Columns should include at least:

```text
question_id
question
k
answer
retrieved_chunk_ids
retrieved_documents
retrieved_pages
retrieval_time_ms
generation_time_ms
total_response_time_ms
answer_accuracy
context_relevance
hallucination_rate
```

Also create:

```text
results/question_level_results.csv
results/comparison_table.csv
```

The comparison table should aggregate results for:

```text
K=1
K=3
K=5
K=10
```

with:

- mean accuracy
- mean context relevance
- mean hallucination rate
- mean response time

Do NOT rank K values as "best" automatically.

The conclusion must come from the measured results.

---

# PART 13 — FAILURE CASE ANALYSIS

Automatically identify interesting failure cases.

Examples:

- More context introduced irrelevant information.
- Top-1 missed an important supporting passage.
- Top-5 retrieved contradictory passages.
- Top-10 increased latency substantially.
- Correct context was retrieved but the LLM ignored it.
- Answer contained unsupported claims.
- Retrieval returned duplicate/near-duplicate chunks.

Create:

```text
results/failure_cases.json
```

Each failure case should include:

```text
question_id
question
k
answer
retrieved_context
metric_values
failure_type
explanation
```

Do not invent explanations unsupported by the retrieved data.

---

# PART 14 — VISUALIZATIONS

Generate publication-quality charts using Python/matplotlib.

Create:

```text
results/figures/
```

Required charts:

1. Answer Accuracy vs K
2. Context Relevance vs K
3. Hallucination Rate vs K
4. Response Time vs K
5. Accuracy distribution by K
6. Hallucination distribution by K
7. Response time distribution by K
8. Question-level K comparison
9. Retrieval similarity distribution
10. Failure case summary

Save figures as PNG and/or SVG.

Use readable labels.

Do not use misleading axes.

Include error bars where statistically meaningful.

---

# PART 15 — STATISTICAL ANALYSIS

Because the same questions are tested at different K values, treat the question as a paired experimental unit.

Where appropriate, implement:

- descriptive statistics
- paired comparisons
- Wilcoxon signed-rank tests

If multiple comparisons are performed, use Holm correction.

Report:

- effect direction
- p-value
- corrected p-value
- effect size if practical

Do not overclaim statistical significance.

If the sample does not justify a statistical conclusion, explicitly say so.

---

# PART 16 — RESEARCH NOTEBOOK

Create:

```text
notebooks/experiment.ipynb
```

The notebook should show:

1. Load processed data
2. Load chunks
3. Load embeddings
4. Load benchmark
5. Run retrieval
6. Generate answers
7. Evaluate
8. Aggregate results
9. Statistical analysis
10. Plot results
11. Inspect failure cases
12. Summarize observations

The notebook must be reproducible.

---

# PART 17 — FASTAPI BACKEND

Create a FastAPI backend.

Structure:

```text
backend/
    app/
        main.py
        schemas.py
        services/
            rag_service.py
            experiment_service.py
            evaluation_service.py
        config.py
```

Endpoints:

```text
GET /health
```

```text
POST /api/query
```

Input:

```json
{
  "question": "...",
  "k": 5
}
```

Output:

```json
{
  "question": "...",
  "k": 5,
  "answer": "...",
  "sources": [],
  "retrieved_chunks": [],
  "metrics": {
    "context_relevance": 0,
    "response_time_ms": 0
  }
}
```

Also:

```text
POST /api/experiment
```

Input:

```json
{
  "question": "..."
}
```

The endpoint should run:

```text
K=1
K=3
K=5
K=10
```

and return all four results.

Also provide:

```text
GET /api/results/summary
GET /api/results/question/{question_id}
```

---

# PART 18 — FRONTEND

Build a polished Next.js + TypeScript frontend.

Use:

- Next.js
- TypeScript
- Tailwind CSS
- Framer Motion where useful
- Recharts for charts
- React Flow if useful for the RAG pipeline visualization

Design language:

Research lab / AI observability dashboard.

Avoid generic SaaS dashboard design.

Use:

- dark interface
- black / charcoal background
- white typography
- subtle red accent
- clean cards
- thin borders
- minimal gradients
- strong typography
- technical/research aesthetic

Do not over-animate.

---

# FRONTEND PAGES

## PAGE 1 — Landing

Hero:

```text
CONTEXTLENS

Does more context make AI smarter?
```

Explain:

> We investigate how retrieval depth changes the quality, faithfulness and latency of Retrieval-Augmented Generation.

Show:

```text
TOP-1
TOP-3
TOP-5
TOP-10
```

as visual cards.

CTA:

```text
Run an Experiment
```

---

## PAGE 2 — Experiment Lab

This is the main page.

Left:

- Question input
- Example questions from benchmark
- Run Experiment button

Right:

RAG pipeline visualization:

```text
Question
   ↓
Embedding
   ↓
Semantic Search
   ↓
Top-K Retrieval
   ↓
LLM
   ↓
Answer
```

After execution show four columns:

```text
TOP-1
TOP-3
TOP-5
TOP-10
```

Each column contains:

- retrieved chunks
- similarity scores
- source document
- page
- generated answer
- answer accuracy
- context relevance
- hallucination rate
- response time

---

# PAGE 3 — CONTEXT INSPECTOR

Show retrieved chunks visually.

For each K:

- Rank
- Document
- Page
- Similarity
- Text

Allow expanding/collapsing chunks.

Highlight the context used by the LLM.

Provide:

```text
Why was this retrieved?
```

with similarity score and metadata.

---

# PAGE 4 — RESEARCH DASHBOARD

Show:

- Answer Accuracy vs K
- Context Relevance vs K
- Hallucination Rate vs K
- Response Time vs K

Also show summary cards:

- Average Accuracy
- Average Context Relevance
- Average Hallucination Rate
- Average Response Time

IMPORTANT:

Do not label one K as "winner" or "best".

Use neutral language such as:

```text
Observed result
Measured change
Difference from K=1
```

---

# PAGE 5 — FAILURE CASES

Display interesting examples.

For each:

- Question
- K=1 answer
- K=3 answer
- K=5 answer
- K=10 answer
- Relevant context
- Failure type
- Metrics

Explain what happened based on evidence.

---

# PAGE 6 — METHODOLOGY

Explain:

- Dataset
- Documents
- Chunking
- Embedding model
- Vector search
- K values
- LLM
- Evaluation metrics
- Experimental design

Include an interactive diagram.

---

# PAGE 7 — ABOUT THE RESEARCH

Show:

- Research question
- Hypothesis
- Experimental setup
- Limitations
- Future work

---

# PART 19 — FRONTEND UX

The UI must feel like an actual research tool.

Add:

- loading states
- skeleton states
- error states
- empty states
- API connection status
- experiment progress indicator
- expandable context
- source badges
- metric tooltips
- responsive layout

For long answers:

use scroll areas.

For metrics:

use compact cards.

For charts:

use clean research-style visualizations.

---

# PART 20 — API CONFIGURATION

Frontend must use:

```text
NEXT_PUBLIC_API_URL
```

Default:

```text
http://localhost:8000
```

Backend:

```text
http://localhost:8000
```

Frontend:

```text
http://localhost:3000
```

---

# PART 21 — DATA VALIDATION

Create:

```text
src/validate_dataset.py
```

It must check:

- all PDFs exist
- extracted pages exist
- chunks exist
- benchmark has exactly 50 questions
- every benchmark question has ground truth
- source documents exist
- source page numbers are valid
- no empty chunks
- no duplicate chunk IDs

Output a validation report.

---

# PART 22 — REPRODUCIBILITY

Create:

```text
.env.example
```

Example:

```text
LLM_PROVIDER=
LLM_MODEL=
OPENAI_API_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Provide documentation for:

- Python version
- Node version
- package versions
- embedding model
- LLM model
- chunk size
- chunk overlap
- retrieval metric
- K values

---

# PART 23 — README

Write a professional README.

Sections:

1. Project title
2. Research question
3. Motivation
4. Key hypothesis
5. Dataset
6. Architecture
7. RAG pipeline
8. Experimental design
9. Evaluation metrics
10. Installation
11. Environment variables
12. Preprocessing
13. Running embeddings
14. Running retrieval
15. Running pilot
16. Running full experiment
17. Starting backend
18. Starting frontend
19. Results
20. Limitations
21. Future work
22. Project structure
23. Reproducibility
24. References

IMPORTANT:

Do not put fabricated final results in README.

Use:

```text
Experiment not yet run.
```

or equivalent until actual results exist.

---

# PART 24 — REQUIREMENTS

Create/update:

```text
requirements.txt
```

Include only packages actually used.

Backend should use FastAPI.

Frontend should have:

```text
package.json
```

with all required dependencies.

---

# PART 25 — GITIGNORE

Include:

```text
.env
.env.*
__pycache__/
*.pyc
node_modules/
.next/
.venv/
venv/
```

Do NOT ignore:

```text
results/*.csv
results/figures/
benchmark files
source code
```

unless there is a specific reason.

---

# PART 26 — PRESENTATION SUPPORT

Create:

```text
presentation/
```

Include a detailed presentation outline/document.

10-slide structure:

### Slide 1
ContextLens

Does More Context Make AI Smarter?

### Slide 2
Problem

### Slide 3
Research Question + Hypothesis

### Slide 4
Dataset + Benchmark

### Slide 5
RAG Architecture

### Slide 6
Experimental Setup

K=1 / 3 / 5 / 10

### Slide 7
Results

### Slide 8
Failure Cases

### Slide 9
Findings + Limitations

### Slide 10
Conclusion + Future Work

Do not fabricate results.

The result slide should automatically correspond to the actual experiment output.

---

# PART 27 — CITATIONS

Use proper academic references for:

- RAG
- retrieval evaluation
- hallucination/faithfulness
- sentence-transformers
- FAISS
- evaluation methodology

Use the actual IIT Roorkee documents as primary data sources.

Do not fabricate citations.

---

# PART 28 — CODE QUALITY

Use:

- Python type hints
- docstrings
- clear function names
- small functions
- proper error handling
- logging
- configuration separation
- no unnecessary global state

Avoid:

- massive single files
- hardcoded paths
- hardcoded API keys
- hardcoded results
- fake metrics
- placeholder backend responses

---

# PART 29 — CRITICAL EXPERIMENTAL RULE

The independent variable is:

```text
RETRIEVAL DEPTH K
```

where:

```text
K ∈ {1, 3, 5, 10}
```

Keep everything else constant:

- same documents
- same preprocessing
- same chunks
- same embedding model
- same vector database
- same similarity metric
- same questions
- same ground truth
- same LLM
- same system prompt
- same generation parameters
- same evaluation methodology

Only K should change.

This is critical for experimental validity.

---

# PART 30 — DO NOT CHEAT

NEVER:

- invent accuracy numbers
- invent hallucination rates
- invent response times
- invent benchmark answers
- invent retrieved passages
- invent statistical significance
- claim that a particular K is best before experiments are actually executed

If the experiment has not been executed, display:

```text
Experiment not yet run.
```

If an API key is unavailable, clearly explain:

```text
LLM generation unavailable. Configure LLM_PROVIDER/LLM_MODEL/API key.
```

Do not silently substitute fake answers.

---

# PART 31 — FINAL EXECUTION

After building the entire project:

1. Install Python dependencies if possible.
2. Install frontend dependencies.
3. Run preprocessing.
4. Run chunking.
5. Generate embeddings.
6. Build FAISS index.
7. Validate benchmark.
8. Run a 5-question × 4-K pilot.
9. Fix any errors.
10. Run the complete 50-question × 4-K experiment if the LLM is configured.
11. Generate CSV files.
12. Generate charts.
13. Start FastAPI.
14. Start Next.js.
15. Test all API endpoints.
16. Test frontend pages.
17. Check for TypeScript errors.
18. Check for Python errors.
19. Check that no fake results exist.
20. Update README with exact run commands.

If an LLM API key is not available, complete EVERYTHING possible without it and leave a clean, documented command for running the generation/evaluation stage later.

---

# FINAL DELIVERABLE

The final project must be a complete repository:

```text
ContextLens/
```

with:

- working Python RAG backend
- FastAPI API
- Next.js frontend
- preprocessing pipeline
- chunking
- embeddings
- FAISS retrieval
- Top-1/3/5/10 experiment
- answer generation
- evaluation
- hallucination analysis
- response-time measurement
- benchmark validation
- statistical analysis
- failure analysis
- charts
- notebook
- README
- requirements
- .env.example
- presentation outline

At the end, provide a concise report containing:

1. Files created/modified
2. Commands to run the project
3. Backend URL
4. Frontend URL
5. Dataset statistics
6. Number of chunks
7. Pilot status
8. Full experiment status
9. Whether an LLM API key is required
10. Any remaining issues

DO NOT STOP after creating the frontend.

DO NOT STOP after creating the Python files.

BUILD THE ENTIRE END-TO-END PROJECT.

Start by inspecting the existing repository and available files, then implement the project systematically.
