"""
PDF preprocessing pipeline.
Extracts text page by page, preserves doc name, page number, cleans artifacts.
Output: data/processed/pages.jsonl
CLI: python -m src.preprocessing
"""
from pathlib import Path
from pypdf import PdfReader
from tqdm import tqdm
import json
from .config import PDF_FILES, PAGES_JSONL, DATA_PROCESSED_DIR
from .utils import clean_text, logger, save_jsonl

def extract_pdf_pages(pdf_path: Path):
    records = []
    try:
        reader = PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        logger.info(f"Processing {pdf_path.name}: {num_pages} pages")
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
                cleaned = clean_text(raw_text)
                # stats
                char_len = len(cleaned)
                word_len = len(cleaned.split())
                # flag very little text
                is_sparse = word_len < 20
                record = {
                    "document": pdf_path.name,
                    "page": page_num,
                    "text": cleaned,
                    "char_count": char_len,
                    "word_count": word_len,
                    "is_sparse": is_sparse,
                    "source_path": str(pdf_path),
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed page {page_num} of {pdf_path.name}: {e}")
                records.append({
                    "document": pdf_path.name,
                    "page": page_num,
                    "text": "",
                    "char_count": 0,
                    "word_count": 0,
                    "is_sparse": True,
                    "source_path": str(pdf_path),
                    "extraction_error": str(e)
                })
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}")
        raise
    return records

def main():
    all_pages = []
    stats = {
        "num_documents": 0,
        "num_pages": 0,
        "total_chars": 0,
        "total_words": 0,
        "sparse_pages": 0,
        "failures": 0,
    }
    for pdf_path in PDF_FILES:
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            continue
        pages = extract_pdf_pages(pdf_path)
        all_pages.extend(pages)

    # compute stats
    stats["num_documents"] = len(set(p["document"] for p in all_pages))
    stats["num_pages"] = len(all_pages)
    stats["total_chars"] = sum(p.get("char_count",0) for p in all_pages)
    stats["total_words"] = sum(p.get("word_count",0) for p in all_pages)
    stats["sparse_pages"] = sum(1 for p in all_pages if p.get("is_sparse"))
    stats["failures"] = sum(1 for p in all_pages if p.get("text","") == "")

    # save
    save_jsonl(PAGES_JSONL, all_pages)
    logger.info(f"Saved {len(all_pages)} pages to {PAGES_JSONL}")

    # validation stats file
    validation_path = DATA_PROCESSED_DIR / "preprocessing_stats.json"
    import json
    with open(validation_path, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Stats: {stats}")

    # print summary
    print("\n=== Preprocessing Summary ===")
    for k,v in stats.items():
        print(f"{k}: {v}")
    print(f"Output: {PAGES_JSONL}")

if __name__ == "__main__":
    main()
