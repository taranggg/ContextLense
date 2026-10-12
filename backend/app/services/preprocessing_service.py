"""
PDF validation and page-by-page text extraction (PyMuPDF).

Page numbers are 1-based physical page indices, i.e. the numbers a PDF viewer
shows in its page counter, not printed page labels.

No OCR is performed. Pages without a text layer are reported as such.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf

from ..schemas import PageRecord

PDF_MIME_TYPES = {"application/pdf", "application/x-pdf"}

_PAGE_NUMBER_RE = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.IGNORECASE)
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")


class PDFValidationError(Exception):
    """A user-facing problem with an uploaded file."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_pdf_upload(filename: str | None, content_type: str | None, head: bytes) -> None:
    """Cheap checks before the file is fully stored: extension, declared MIME type, magic bytes."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise PDFValidationError("invalid_extension", "Only .pdf files are supported.")
    if content_type and content_type.split(";")[0].strip().lower() not in PDF_MIME_TYPES:
        raise PDFValidationError("invalid_mime_type", f"Expected a PDF, but the file was sent as '{content_type}'.")
    if b"%PDF-" not in head[:1024]:
        raise PDFValidationError("not_a_pdf", "This file does not look like a PDF (missing PDF header).")


def inspect_pdf(path: Path) -> int:
    """Open the file with PyMuPDF to confirm it parses. Returns the page count."""
    try:
        with pymupdf.open(str(path)) as doc:
            if not doc.is_pdf:
                raise PDFValidationError("not_a_pdf", "The file could not be read as a PDF.")
            if doc.needs_pass:
                raise PDFValidationError("encrypted", "This PDF is password-protected. Remove the password and upload it again.")
            if doc.page_count == 0:
                raise PDFValidationError("empty_pdf", "This PDF has no pages.")
            return doc.page_count
    except PDFValidationError:
        raise
    except Exception as exc:  # PyMuPDF raises various error types for corrupt files
        raise PDFValidationError("unreadable_pdf", "The PDF appears to be damaged and could not be opened.") from exc


def clean_paragraph(text: str) -> str:
    """Normalise one extracted text block into a single paragraph string."""
    text = unicodedata.normalize("NFKC", text)  # expands ligatures such as "ﬁ"
    text = text.replace("­", "")  # soft hyphens
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK_RE.sub(lambda m: m.group(1) + m.group(2) if m.group(2).islower() else m.group(0), text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def _is_artifact(paragraph: str) -> bool:
    stripped = paragraph.strip()
    return len(stripped) < 2 or bool(_PAGE_NUMBER_RE.match(stripped))


def _repeated_boilerplate(pages_blocks: list[list[str]]) -> set[str]:
    """Short blocks that recur on most pages (running headers/footers)."""
    if len(pages_blocks) < 4:
        return set()
    counts: Counter[str] = Counter()
    for blocks in pages_blocks:
        counts.update({b.lower() for b in blocks if len(b) <= 100})
    threshold = max(3, int(0.6 * len(pages_blocks)))
    return {text for text, n in counts.items() if n >= threshold}


def extract_pages(pdf_path: Path, document_id: str, document_name: str, min_page_words: int = 5) -> list[PageRecord]:
    """Extract paragraphs page by page. Every returned record carries document and page metadata."""
    pages_blocks: list[list[str]] = []
    with pymupdf.open(str(pdf_path)) as doc:
        for page in doc:
            blocks = page.get_text("blocks", sort=True, flags=pymupdf.TEXTFLAGS_TEXT)
            paragraphs = []
            for block in blocks:
                if block[6] != 0:  # 1 = image block
                    continue
                para = clean_paragraph(block[4])
                if para and not _is_artifact(para):
                    paragraphs.append(para)
            pages_blocks.append(paragraphs)

    boilerplate = _repeated_boilerplate(pages_blocks)
    records: list[PageRecord] = []
    for page_number, paragraphs in enumerate(pages_blocks, start=1):
        kept = [p for p in paragraphs if p.lower() not in boilerplate]
        text = "\n\n".join(kept)
        words = len(text.split())
        records.append(
            PageRecord(
                document_id=document_id,
                document_name=document_name,
                page=page_number,
                text=text,
                paragraphs=kept,
                word_count=words,
                has_text=words >= min_page_words,
            )
        )
    return records
