# Data Directory

## Structure
```
data/
├── raw/
│   ├── Information_Brochure_2026.pdf  # PG Information Brochure 2026 (M.Tech/M.Arch/MURP)
│   └── PhD_IB_A2026.pdf               # Ph.D. Information Brochure Autumn 2026
├── processed/
│   ├── pages.jsonl    # Page-level extracted text with metadata
│   └── chunks.jsonl   # 500-word chunks with 80-word overlap
└── benchmark/
    ├── ContextLens_Benchmark_50_Questions.json
    └── ContextLens_Benchmark_50_Questions.csv
```

## Source Documents
- **Information_Brochure_2026.pdf**: 25 pages, PG admissions, eligibility, sponsored categories, application process
- **PhD_IB_A2026.pdf**: 37 pages, PhD admission requirements, departments, MEQ, categories (FTRS, PTRS, Golden Girl etc.)

Both sourced from official IIT Roorkee website (https://iitr.ac.in).

## Benchmark Composition (50 Questions)
- 15 direct factual
- 10 procedural
- 10 eligibility
- 5 conditional
- 5 numerical
- 5 multi-part

Each question contains: question_id, question, category, ground_truth, required_facts, source_document, source_page (approx), difficulty.

## Preprocessing Notes
- Extraction uses pypdf with artifact cleaning
- Hyphenated line breaks fixed
- Paragraph boundaries preserved
- Same chunks used for all K values (experimental validity)
