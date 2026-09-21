"""Utility helpers"""
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("contextlens")

def clean_text(text: str) -> str:
    """Clean PDF artifacts"""
    if not text:
        return ""
    # Fix hyphenated line breaks: word- \n word -> wordword or word word?
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    # Normalize whitespace but preserve paragraphs (double newline)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove excessive spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove isolated page numbers / headers footers heuristics: lines with only numbers
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # skip lines that are just numbers (page numbers)
        if re.fullmatch(r'\d{1,3}', stripped):
            continue
        # skip very short artifact lines like "IIT Roorkee 2026" repeated? Keep if >3 chars
        if len(stripped) < 2:
            continue
        lines.append(stripped)
    # Rejoin with paragraph detection: if line ends with period, keep break
    cleaned = "\n".join(lines)
    # Collapse 3+ newlines to 2
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    # Remove excessive whitespace around
    cleaned = cleaned.strip()
    return cleaned

def word_count(text: str) -> int:
    return len(text.split())

def chunk_id_hash(doc: str, page: int, idx: int, text_snippet: str) -> str:
    base = f"{doc}_{page}_{idx}_{text_snippet[:50]}"
    return hashlib.md5(base.encode()).hexdigest()[:12]

def load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                items.append(json.loads(line))
    return items

def save_jsonl(path: Path, items: List[Dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

def load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def truncate_text(text: str, max_words: int = 100) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."
