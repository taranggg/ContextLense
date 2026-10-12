# Data directory

Everything ContextLens stores lives here (configurable with `DATA_DIR`).

```text
data/
├── contextlens.db              SQLite: document metadata, processing status, saved research comparisons
├── documents/<document-id>/    one folder per uploaded PDF (git-ignored)
│   ├── source.pdf              the upload, stored under a generated name
│   ├── pages.jsonl             text extracted page by page (PyMuPDF), with page numbers
│   ├── chunks.jsonl            ~500-word passages with 80-word overlap and their page numbers
│   ├── embeddings.npy          L2-normalised all-MiniLM-L6-v2 vectors, one row per chunk
│   ├── index.faiss             exact inner-product index (= cosine similarity)
│   └── index_meta.json         embedding model, dimension and chunk-id order
├── raw/                        bundled sample PDFs used by the research benchmark
└── benchmark/
    ├── ContextLens_Benchmark_50_Questions.json / .csv
    └── validation_report.json  automatic check of each question's cited page
```

Deleting a document in the app removes its folder, its metadata row and any saved
research comparisons that used it. Nothing is encrypted at rest.

## Sample documents

- `Information_Brochure_2026.pdf` — IIT Roorkee PG admissions brochure, 25 pages
  (<https://ir.iitr.ac.in/pdf/PG_Information_Brochure_2026.pdf>)
- `PhD_IB_A2026.pdf` — IIT Roorkee Ph.D. admissions brochure (Autumn 2026), 37 pages

They appear in the app labelled "Sample" after `python -m backend.app.research.benchmark ingest`.

## Benchmark

50 questions (15 factual, 10 procedural, 10 eligibility, 5 conditional, 5 numerical,
5 multi-part). The file's own metadata says it was **generated from the PDFs**, not
written by domain experts, and its `source_page` values were assigned by keyword
search. `validation_report.json` records, for each question, whether its required
facts actually appear on the cited page of the PyMuPDF text. The benchmark file
itself is never modified.
