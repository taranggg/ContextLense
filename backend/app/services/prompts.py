"""Prompt templates. Changing them changes experimental conditions, so bump PROMPT_VERSION."""
from __future__ import annotations

import re

from ..schemas import RetrievedChunk

PROMPT_VERSION = "rag-v4"

ABSTAIN_SENTENCE = "I couldn't find enough evidence in the selected documents to answer this."

RAG_SYSTEM_PROMPT = f"""You are ContextLens, a strict academic assistant. You answer questions using ONLY the provided document excerpts.

CRITICAL INSTRUCTIONS:
1. ZERO OUTSIDE KNOWLEDGE: If the answer is not in the provided sources, start your response with exactly: "{ABSTAIN_SENTENCE}"
2. REQUIRED STRUCTURE: You MUST format every single response using this exact Markdown template:
   
   ### [Insert a relevant short header based on the question]
   
   **Key Takeaways:**
   * [Insert fact 1] [S#].
   * [Insert fact 2] [S#].
   
   **Conclusion:** [Insert a brief summary or final note based entirely on the sources] [S#].

3. SENTENCE-LEVEL CITATIONS: You MUST append the exact source marker in brackets at the end of EVERY single bullet point and sentence. 
   - Correct: The application fee is ₹500 [S1].
   - Incorrect: The application fee is ₹500. (Missing citation before period).
4. NO CLUMPING: Never group citations at the end of a section (e.g., [S1][S2]). Each claim must be cited individually.
5. NO FAKE SOURCES: Only use the [S#] tags explicitly provided in the text below.
6. INFERENCES: If you state a conclusion implied (but not explicitly stated) by the sources, prefix the sentence with "Inference:"."""

NO_RAG_SYSTEM_PROMPT = """Answer the question from your general knowledge. If you do not know the answer or are unsure, say so plainly instead of guessing. Be concise: a few sentences or a short list."""


def format_pages(pages: list[int]) -> str:
    if len(pages) == 1:
        return f"page {pages[0]}"
    if pages == list(range(pages[0], pages[-1] + 1)):
        return f"pages {pages[0]}–{pages[-1]}"
    return "pages " + ", ".join(str(p) for p in pages)


def build_rag_messages(
    question: str,
    sources: list[RetrievedChunk],
    texts: list[str] | None = None,
    history: list[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    `texts` optionally overrides each source's text (used when trimming to fit the context window).
    `history` is prior (question, answer) pairs from the same conversation, oldest first, added as
    separate turns so the model can resolve follow-ups ("what about page 2?") against them.
    """
    blocks = []
    for i, src in enumerate(sources):
        text = texts[i] if texts is not None else src.text
        blocks.append(f"[{src.source_label}] {src.document_name}, {format_pages(src.pages)}\n{text}")
    user = "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
    for prior_question, prior_answer in history or []:
        messages.append({"role": "user", "content": prior_question})
        messages.append({"role": "assistant", "content": prior_answer})
    messages.append({"role": "user", "content": user})
    return messages


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
