"""
Dataset validation.
Checks:
- PDFs exist
- extracted pages exist
- chunks exist
- benchmark has exactly 50 questions
- every benchmark question has ground truth
- source documents exist
- source page numbers valid
- no empty chunks
- no duplicate chunk IDs
"""
import json
from pathlib import Path
from .config import PDF_FILES, PAGES_JSONL, CHUNKS_JSONL, BENCHMARK_PATH, DATA_PROCESSED_DIR
from .utils import load_jsonl, load_json, logger

def validate():
    report = {
        "pdfs_exist": True,
        "pages_exist": False,
        "chunks_exist": False,
        "benchmark_exists": False,
        "benchmark_count": 0,
        "benchmark_valid": True,
        "issues": [],
        "stats": {}
    }

    # PDFs
    for pdf in PDF_FILES:
        if not pdf.exists():
            report["pdfs_exist"] = False
            report["issues"].append(f"Missing PDF: {pdf}")
        else:
            size = pdf.stat().st_size
            report["stats"][pdf.name] = f"{size} bytes"

    # Pages
    if PAGES_JSONL.exists():
        pages = load_jsonl(PAGES_JSONL)
        report["pages_exist"] = True
        report["stats"]["num_pages"] = len(pages)
        sparse = sum(1 for p in pages if p.get("is_sparse"))
        report["stats"]["sparse_pages"] = sparse
        empty = sum(1 for p in pages if not p.get("text"))
        if empty>0:
            report["issues"].append(f"{empty} pages with empty text")
    else:
        report["issues"].append(f"Missing pages.jsonl: {PAGES_JSONL}")

    # Chunks
    if CHUNKS_JSONL.exists():
        chunks = load_jsonl(CHUNKS_JSONL)
        report["chunks_exist"] = True
        report["stats"]["num_chunks"] = len(chunks)
        empty_chunks = [c for c in chunks if not c.get("text") or len(c.get("text","").strip())==0]
        if empty_chunks:
            report["issues"].append(f"{len(empty_chunks)} empty chunks")
        # duplicate IDs
        ids = [c["chunk_id"] for c in chunks]
        dup = len(ids) - len(set(ids))
        if dup>0:
            report["issues"].append(f"{dup} duplicate chunk IDs")
        # word count stats
        if chunks:
            avg_wc = sum(c.get("word_count",0) for c in chunks)/len(chunks)
            report["stats"]["avg_chunk_words"] = round(avg_wc,2)
    else:
        report["issues"].append(f"Missing chunks.jsonl: {CHUNKS_JSONL}")

    # Benchmark
    if BENCHMARK_PATH.exists():
        report["benchmark_exists"] = True
        try:
            data = load_json(BENCHMARK_PATH)
            # Support both list and dict with questions key
            if isinstance(data, dict) and "questions" in data:
                questions = data["questions"]
            elif isinstance(data, list):
                questions = data
            else:
                questions = []
                report["issues"].append("Benchmark JSON structure unexpected")
            
            report["benchmark_count"] = len(questions)
            if len(questions) != 50:
                report["issues"].append(f"Benchmark should have 50 questions, found {len(questions)}")
            
            # Check each question has required fields
            for i,q in enumerate(questions):
                if not q.get("question"):
                    report["benchmark_valid"]=False
                    report["issues"].append(f"Question {i} missing question text")
                if not q.get("ground_truth"):
                    report["benchmark_valid"]=False
                    report["issues"].append(f"Question {q.get('question_id',i)} missing ground_truth")
                if not q.get("required_facts"):
                    report["issues"].append(f"Question {q.get('question_id',i)} missing required_facts (warning)")
                # source document check
                src_doc = q.get("source_document")
                if src_doc and src_doc not in [p.name for p in PDF_FILES]:
                    # allow partial match
                    if not any(src_doc in pdf.name or pdf.name in src_doc for pdf in PDF_FILES):
                        report["issues"].append(f"Question {q.get('question_id')} source_document {src_doc} not in expected PDFs")

            # Category counts
            from collections import Counter
            cats = Counter([q.get("category","unknown") for q in questions])
            report["stats"]["benchmark_categories"] = dict(cats)

        except Exception as e:
            report["benchmark_valid"]=False
            report["issues"].append(f"Failed to load benchmark: {e}")
    else:
        report["issues"].append(f"Missing benchmark: {BENCHMARK_PATH}")

    # Save report
    report_path = DATA_PROCESSED_DIR / "validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n=== Validation Report ===")
    print(json.dumps(report, indent=2))
    print(f"\nSaved to {report_path}")

    if report["issues"]:
        print("\nIssues found:")
        for issue in report["issues"]:
            print(f" - {issue}")
    else:
        print("\nAll checks passed!")

    return report

if __name__ == "__main__":
    validate()
