"""Prompt templates. Changing them changes experimental conditions, so bump PROMPT_VERSION."""
from __future__ import annotations

import re

from ..schemas import RetrievedChunk

PROMPT_VERSION = "rag-v1"

ABSTAIN_SENTENCE = "I couldn't find enough evidence in the selected documents to answer this."

RAG_SYSTEM_PROMPT = f"""You are ContextLens, an assistant that answers questions using only excerpts from documents the user provided.

Rules:
1. Use only the information in the provided sources. Do not use outside knowledge.
2. Cite every factual statement with the marker of the source it came from, for example [S1] or [S2][S3]. Only use markers that appear in the sources. Never invent sources, page numbers or document names.
3. If the sources do not contain enough information to answer, begin your reply with exactly: "{ABSTAIN_SENTENCE}" Then briefly mention any closely related information the sources do contain, with citations.
4. If you state a conclusion that the sources imply but do not say directly, prefix that sentence with "Inference:".
5. Be concise: a few sentences or a short list, unless the user asks for detail.
6. Use plain text or simple Markdown (paragraphs, bullet lists, bold). Do not add a separate references section."""

NO_RAG_SYSTEM_PROMPT = """Answer the question from your general knowledge. If you do not know the answer or are unsure, say so plainly instead of guessing. Be concise: a few sentences or a short list."""


def format_pages(pages: list[int]) -> str:
    if len(pages) == 1:
        return f"page {pages[0]}"
    if pages == list(range(pages[0], pages[-1] + 1)):
        return f"pages {pages[0]}–{pages[-1]}"
    return "pages " + ", ".join(str(p) for p in pages)


def build_rag_messages(question: str, sources: list[RetrievedChunk], texts: list[str] | None = None) -> list[dict[str, str]]:
    """`texts` optionally overrides each source's text (used when trimming to fit the context window)."""
    blocks = []
    for i, src in enumerate(sources):
        text = texts[i] if texts is not None else src.text
        blocks.append(f"[{src.source_label}] {src.document_name}, {format_pages(src.pages)}\n{text}")
    user = "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    return [{"role": "system", "content": RAG_SYSTEM_PROMPT}, {"role": "user", "content": user}]


def build_no_rag_messages(question: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": NO_RAG_SYSTEM_PROMPT}, {"role": "user", "content": question}]


_ABSTAIN_RE = re.compile(
    r"(?:(?:could ?n[o']?t|can ?not|can'?t|unable to|did ?n[o']?t|do ?n[o']?t) find (?:enough|sufficient|any) (?:evidence|information)"
    r"|(?:do|does) not (?:contain|provide|include) (?:enough|sufficient) (?:evidence|information))",
    re.IGNORECASE,
)


def is_abstention(answer: str) -> bool:
    """True when the answer declines for lack of evidence (checked near the start of the answer)."""
    return bool(_ABSTAIN_RE.search(answer[:400].replace("’", "'")))
