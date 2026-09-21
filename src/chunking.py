"""
Section-aware chunking: ~500 words per chunk, ~80 words overlap, paragraph boundaries.
Same chunks used for all K experiments.
Output: data/processed/chunks.jsonl
CLI: python -m src.chunking
"""
from pathlib import Path
from typing import List, Dict
import re
from .config import PAGES_JSONL, CHUNKS_JSONL, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS, DATA_PROCESSED_DIR
from .utils import load_jsonl, save_jsonl, chunk_id_hash, logger, word_count
import json

def split_into_paragraphs(text: str) -> List[str]:
    # Split by double newline or period+newline heuristics
    # First try double newline
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    # If still huge paragraphs, split by sentences? Keep simple
    # Further split very long lines by sentence boundaries if >200 words
    final_paras = []
    for para in paras:
        words = para.split()
        if len(words) > 300:
            # split by sentence endings
            sentences = re.split(r'(?<=[.!?])\s+', para)
            curr = ""
            curr_words = 0
            for sent in sentences:
                sw = len(sent.split())
                if curr_words + sw > 150 and curr:
                    final_paras.append(curr.strip())
                    curr = sent
                    curr_words = sw
                else:
                    curr = (curr + " " + sent).strip() if curr else sent
                    curr_words += sw
            if curr:
                final_paras.append(curr.strip())
        else:
            final_paras.append(para)
    return final_paras

def create_chunks_from_pages(pages: List[Dict], chunk_size: int = 500, overlap: int = 80) -> List[Dict]:
    chunks = []
    chunk_idx_global = 0

    for page_record in pages:
        doc = page_record["document"]
        page_num = page_record["page"]
        text = page_record.get("text","")
        if not text or page_record.get("is_sparse"):
            continue

        paragraphs = split_into_paragraphs(text)
        # Build chunks within page first, then allow cross-page? Requirement says do not merge unrelated pages.
        # So we keep page boundary as hard stop, but overlap within page.
        current_chunk_words = []
        current_chunk_paras = []
        para_cursor = 0

        while para_cursor < len(paragraphs):
            para = paragraphs[para_cursor]
            para_words = para.split()
            # If adding para exceeds chunk_size and we already have content, finalize chunk
            if len(current_chunk_words) + len(para_words) > chunk_size and current_chunk_words:
                chunk_text = " ".join(current_chunk_words)
                wc = len(current_chunk_words)
                cid = chunk_id_hash(doc, page_num, chunk_idx_global, chunk_text)
                chunks.append({
                    "chunk_id": cid,
                    "document": doc,
                    "page": page_num,
                    "text": chunk_text,
                    "word_count": wc,
                    "paragraph_count": len(current_chunk_paras),
                    "source_pages": [page_num],
                })
                chunk_idx_global += 1
                # overlap: keep last `overlap` words
                if overlap > 0 and wc > overlap:
                    overlap_words = current_chunk_words[-overlap:]
                    current_chunk_words = overlap_words.copy()
                    # approximate paras for overlap not precise, reset
                    current_chunk_paras = []
                else:
                    current_chunk_words = []
                    current_chunk_paras = []
                # Do not increment para_cursor, retry adding same para to new chunk
                continue
            else:
                current_chunk_words.extend(para_words)
                current_chunk_paras.append(para)
                para_cursor += 1

        # flush remaining
        if current_chunk_words:
            chunk_text = " ".join(current_chunk_words)
            wc = len(current_chunk_words)
            # Filter very small chunks (<50 words) unless it's the only chunk from page
            if wc >= 30:
                cid = chunk_id_hash(doc, page_num, chunk_idx_global, chunk_text)
                chunks.append({
                    "chunk_id": cid,
                    "document": doc,
                    "page": page_num,
                    "text": chunk_text,
                    "word_count": wc,
                    "paragraph_count": len(current_chunk_paras),
                    "source_pages": [page_num],
                })
                chunk_idx_global += 1

    # Second pass: merge tiny chunks with previous if same document/page? Already filtered
    return chunks

def main():
    if not PAGES_JSONL.exists():
        logger.error(f"Pages file not found: {PAGES_JSONL}. Run preprocessing first.")
        return

    pages = load_jsonl(PAGES_JSONL)
    logger.info(f"Loaded {len(pages)} pages")

    chunks = create_chunks_from_pages(pages, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
    logger.info(f"Created {len(chunks)} chunks")

    # stats
    total_words = sum(c["word_count"] for c in chunks)
    avg_words = total_words / len(chunks) if chunks else 0
    min_words = min((c["word_count"] for c in chunks), default=0)
    max_words = max((c["word_count"] for c in chunks), default=0)

    # duplicate check
    chunk_ids = [c["chunk_id"] for c in chunks]
    duplicates = len(chunk_ids) - len(set(chunk_ids))

    stats = {
        "num_chunks": len(chunks),
        "total_words": total_words,
        "avg_words": round(avg_words,2),
        "min_words": min_words,
        "max_words": max_words,
        "duplicate_ids": duplicates,
        "chunk_size_target": CHUNK_SIZE_WORDS,
        "overlap_target": CHUNK_OVERLAP_WORDS,
        "documents": list(set(c["document"] for c in chunks)),
    }

    save_jsonl(CHUNKS_JSONL, chunks)
    logger.info(f"Saved chunks to {CHUNKS_JSONL}")

    stats_path = DATA_PROCESSED_DIR / "chunking_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print("\n=== Chunking Summary ===")
    for k,v in stats.items():
        print(f"{k}: {v}")
    print(f"Output: {CHUNKS_JSONL}")

if __name__ == "__main__":
    main()
