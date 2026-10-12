"""
Paragraph-aware chunking.

- Paragraphs are packed into chunks of up to `chunk_size` words.
- Consecutive chunks share roughly `overlap` words, taken from whole trailing
  paragraphs where possible (falling back to the last words of one paragraph).
- Chunks may continue across adjacent pages of the same document; every page
  that contributes text is listed in `pages`.
- Pages without extractable text are skipped.
- Chunk IDs are deterministic: the same document and settings produce the same IDs.
- Chunking is done once per document; every K setting reads the same chunks.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..schemas import Chunk, PageRecord

_SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+")


@dataclass(frozen=True)
class _Unit:
    words: tuple[str, ...]
    page: int


def _split_long(words: list[str], page: int, max_words: int) -> list[_Unit]:
    """Split a paragraph longer than max_words at sentence boundaries, then by words if needed."""
    if len(words) <= max_words:
        return [_Unit(tuple(words), page)]
    sentences = _SENTENCE_RE.split(" ".join(words))
    units: list[_Unit] = []
    current: list[str] = []
    for sentence in sentences:
        s_words = sentence.split()
        while len(s_words) > max_words:  # one huge "sentence"
            if current:
                units.append(_Unit(tuple(current), page))
                current = []
            units.append(_Unit(tuple(s_words[:max_words]), page))
            s_words = s_words[max_words:]
        if current and len(current) + len(s_words) > max_words:
            units.append(_Unit(tuple(current), page))
            current = []
        current.extend(s_words)
    if current:
        units.append(_Unit(tuple(current), page))
    return units


def _units_from_pages(pages: list[PageRecord], max_unit_words: int) -> list[_Unit]:
    units: list[_Unit] = []
    for page in sorted(pages, key=lambda p: p.page):
        if not page.has_text:
            continue
        paragraphs = page.paragraphs or [p for p in page.text.split("\n\n") if p.strip()]
        for para in paragraphs:
            words = para.split()
            if words:
                units.extend(_split_long(words, page.page, max_unit_words))
    return units


def _overlap_tail(units: list[_Unit], overlap: int) -> list[_Unit]:
    """Trailing whole paragraphs totalling <= overlap words; else the last `overlap` words of the last one."""
    if overlap <= 0 or not units:
        return []
    tail: list[_Unit] = []
    total = 0
    for unit in reversed(units):
        if total + len(unit.words) > overlap:
            break
        tail.insert(0, unit)
        total += len(unit.words)
    if tail and len(tail) < len(units):
        return tail
    last = units[-1]
    return [_Unit(last.words[-overlap:], last.page)]


def make_chunk_id(document_id: str, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{document_id}-c{index:04d}-{digest}"


def chunk_pages(
    pages: list[PageRecord],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")
    if not pages:
        return []

    document_id = pages[0].document_id
    document_name = pages[0].document_name
    # Units are capped so that overlap + one new unit always fits in a chunk.
    units = _units_from_pages(pages, max(1, chunk_size - overlap))

    groups: list[list[_Unit]] = []
    current: list[_Unit] = []
    current_words = 0
    has_new_content = False
    for unit in units:
        if has_new_content and current_words + len(unit.words) > chunk_size:
            groups.append(current)
            current = _overlap_tail(current, overlap)
            current_words = sum(len(u.words) for u in current)
            has_new_content = False
        current.append(unit)
        current_words += len(unit.words)
        has_new_content = True
    if current and has_new_content:
        groups.append(current)

    chunks: list[Chunk] = []
    for index, group in enumerate(groups):
        parts: list[str] = []
        page_starts: list[tuple[int, int]] = []
        offset = 0
        for unit in group:
            if not page_starts or page_starts[-1][1] != unit.page:
                page_starts.append((offset, unit.page))
            piece = " ".join(unit.words)
            parts.append(piece)
            offset += len(piece) + 2  # "\n\n" separator
        text = "\n\n".join(parts)
        chunks.append(
            Chunk(
                chunk_id=make_chunk_id(document_id, index, text),
                document_id=document_id,
                document_name=document_name,
                index=index,
                pages=sorted({u.page for u in group}),
                text=text,
                word_count=sum(len(u.words) for u in group),
                page_starts=page_starts,
            )
        )
    return chunks
