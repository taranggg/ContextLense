"""
Retrieval-augmented generation.

1. Check that the selected documents exist and are ready.
2. Retrieve Top-K chunks (cosine similarity).
3. Build a prompt that labels each chunk [S1]..[Sk] with its document and pages.
4. Generate with the local LLM.
5. Map [S#] markers in the answer back to retrieved chunk metadata. Markers that
   do not match a supplied source are reported as invalid, never shown as citations.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Optional

from ..config import Settings
from ..schemas import (
    ChatResponse,
    Citation,
    DocumentStatus,
    GenerationStats,
    Latency,
    ModelInfo,
    RetrievedChunk,
)
from ..storage.document_files import is_valid_document_id
from ..storage.metadata_store import MetadataStore
from .llm_service import GenerationParams, GenerationResult, LLMBackend
from .prompts import build_no_rag_messages, build_rag_messages, is_abstention
from .retrieval_service import RetrievalService

logger = logging.getLogger("contextlens.rag")

_CITATION_RE = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S?\d+)*)\s*\]", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9.%]*", re.IGNORECASE)  # hyphens/slashes split terms: "full-time" -> full, time
_STOPWORDS = frozenset(
    "the a an and or of to in on for with by at from is are was were be been being this that these those it its "
    "as which who whom what when where why how do does did can could should would will shall may might must not "
    "no yes if then than there their they them he she his her you your we our i me my about into over under such "
    "any all each per via also only other more most some".split()
)
_MIN_SOURCE_WORDS = 30


class DocumentsNotReadyError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d{2,3}\b)")


def content_terms(text: str) -> set[str]:
    """Lower-cased content words; digit grouping is normalised ("5,000" -> "5000", "1,00,000" -> "100000")."""
    text = _THOUSANDS_RE.sub("", text)
    terms = {w.lower().strip(".") for w in _WORD_RE.findall(text)}
    return {t for t in terms if t and t not in _STOPWORDS and len(t) > 1}


def parse_citation_labels(answer: str) -> list[str]:
    """All [S#] markers in order of first appearance, e.g. '[S1, S3]' -> ['S1', 'S3']."""
    labels: list[str] = []
    for match in _CITATION_RE.finditer(answer):
        for part in re.split(r"[,;]", match.group(1)):
            num = re.sub(r"\D", "", part)
            if num:
                label = f"S{int(num)}"
                if label not in labels:
                    labels.append(label)
    return labels


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for sep in _SENTENCE_RE.finditer(text):
        if text[start : sep.start()].strip():
            spans.append((start, sep.start()))
        start = sep.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def pages_for_span(page_starts: list[tuple[int, int]], start: int, end: int, fallback: list[int]) -> list[int]:
    """Pages whose text overlaps the character range [start, end) of a chunk."""
    if not page_starts:
        return fallback
    pages = []
    for i, (offset, page) in enumerate(page_starts):
        next_offset = page_starts[i + 1][0] if i + 1 < len(page_starts) else float("inf")
        if offset < end and next_offset > start and page not in pages:
            pages.append(page)
    return pages or fallback


def best_excerpt(text: str, focus: str, max_words: int = 70) -> tuple[str, int, int]:
    """The window of up to 3 sentences sharing the most content terms with `focus`, plus its character span."""
    spans = _sentence_spans(text)
    if not spans:
        return "", 0, 0
    focus_terms = content_terms(focus)
    best, best_score = 0, -1
    for i in range(len(spans)):
        window = text[spans[i][0] : spans[min(i + 2, len(spans) - 1)][1]]
        score = len(content_terms(window) & focus_terms)
        if score > best_score:
            best, best_score = i, score
    start, end = spans[best][0], spans[min(best + 2, len(spans) - 1)][1]
    words = list(re.finditer(r"\S+", text[start:end]))
    clipped = len(words) > max_words
    if clipped:
        end = start + words[max_words - 1].end()
    excerpt = " ".join(text[start:end].split())
    prefix = "… " if start > 0 else ""
    suffix = " …" if clipped or end < len(text.rstrip()) else ""
    return prefix + excerpt + suffix, start, end


def build_citations(answer: str, question: str, sources: list[RetrievedChunk]) -> tuple[list[Citation], list[str]]:
    by_label = {s.source_label: s for s in sources}
    citations: list[Citation] = []
    invalid: list[str] = []
    answer_sentences = _SENTENCE_RE.split(answer)
    for label in parse_citation_labels(answer):
        src = by_label.get(label)
        if src is None:
            invalid.append(label)
            continue
        citing_parts = []
        for i, sentence in enumerate(answer_sentences):
            if label in parse_citation_labels(sentence):
                body = _CITATION_RE.sub(" ", sentence).strip()
                if not body and i > 0:  # marker placed after the full stop: "…2001. [S5]"
                    body = _CITATION_RE.sub(" ", answer_sentences[i - 1])
                citing_parts.append(body)
        focus = f"{question} {' '.join(citing_parts)}"
        excerpt, start, end = best_excerpt(src.text, focus)
        citations.append(
            Citation(
                source_label=label,
                rank=src.rank,
                chunk_id=src.chunk_id,
                document_id=src.document_id,
                document_name=src.document_name,
                pages=src.pages,
                excerpt_pages=pages_for_span(src.page_starts, start, end, src.pages),
                similarity=src.similarity,
                excerpt=excerpt,
            )
        )
    return citations, invalid


class RAGService:
    def __init__(self, settings: Settings, store: MetadataStore, retrieval: RetrievalService, llm: LLMBackend):
        self.settings = settings
        self.store = store
        self.retrieval = retrieval
        self.llm = llm

    # ------------------------------------------------------------------ helpers

    @property
    def params(self) -> GenerationParams:
        return GenerationParams(
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
            top_p=self.settings.llm_top_p,
        )

    def model_info(self) -> ModelInfo:
        return ModelInfo(
            runtime=self.llm.runtime,
            model=self.llm.model_id,
            temperature=self.settings.llm_temperature,
            top_p=self.settings.llm_top_p,
            max_tokens=self.settings.llm_max_tokens,
            context_tokens=self.settings.llm_context_tokens,
        )

    def check_documents(self, document_ids: list[str]) -> list[str]:
        ids = list(dict.fromkeys(document_ids))
        if not ids:
            raise DocumentsNotReadyError("no_documents", "Select at least one document.")
        names = []
        for doc_id in ids:
            doc = self.store.get_document(doc_id) if is_valid_document_id(doc_id) else None
            if doc is None:
                raise DocumentsNotReadyError("document_not_found", "One of the selected documents no longer exists.")
            if doc.status != DocumentStatus.ready:
                raise DocumentsNotReadyError(
                    "document_not_ready", f"'{doc.filename}' is not ready yet (status: {doc.status.value})."
                )
            names.append(doc.filename)
        return names

    def resolve_k(self, k: Optional[int]) -> int:
        k = k or self.settings.default_top_k
        if not 1 <= k <= self.settings.max_top_k:
            raise ValueError(f"k must be between 1 and {self.settings.max_top_k}.")
        return k

    def _fit_context(
        self, question: str, sources: list[RetrievedChunk], history: Optional[list[tuple[str, str]]] = None
    ) -> tuple[list[dict[str, str]], int, bool]:
        """Trim the lowest-ranked sources until the prompt fits the context budget."""
        budget = self.settings.llm_context_tokens - self.settings.llm_max_tokens - 64
        texts = [s.text for s in sources]
        n = len(sources)
        truncated = False
        messages = build_rag_messages(question, sources[:n], texts[:n], history)
        tokens = self.llm.count_tokens(messages)
        while tokens > budget and n > 0:
            truncated = True
            words = texts[n - 1].split()
            excess_words = int((tokens - budget) / 1.3) + 10
            keep = len(words) - excess_words
            if keep < _MIN_SOURCE_WORDS:
                n -= 1
            else:
                texts[n - 1] = " ".join(words[:keep]) + " …"
            messages = build_rag_messages(question, sources[:n], texts[:n], history)
            tokens = self.llm.count_tokens(messages)
        if truncated:
            logger.info("Context trimmed to fit %d tokens (%d of %d sources kept)", budget, n, len(sources))
        return messages, n, truncated

    # ------------------------------------------------------------------ main entry points

    def retrieve(self, question: str, document_ids: list[str], k: int):
        return self.retrieval.retrieve(question, document_ids, k)

    def answer_from_sources(
        self,
        question: str,
        sources: list[RetrievedChunk],
        k: int,
        retrieval_ms: float,
        on_token: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        history: Optional[list[tuple[str, str]]] = None,
    ) -> ChatResponse:
        start = time.perf_counter()
        messages, n_in_prompt, truncated = self._fit_context(question, sources, history)
        result: GenerationResult = self.llm.generate(messages, self.params, on_token=on_token, should_stop=should_stop)
        included = sources[:n_in_prompt]
        citations, invalid = build_citations(result.text, question, included)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return ChatResponse(
            question=question,
            answer=result.text,
            abstained=is_abstention(result.text),
            citations=citations,
            invalid_citations=invalid,
            retrieved=sources,
            k=k,
            latency=Latency(
                retrieval_ms=round(retrieval_ms, 2),
                generation_ms=round(result.generation_ms, 2),
                total_ms=round(retrieval_ms + elapsed_ms, 2),
            ),
            model=self.model_info(),
            generation=GenerationStats(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                finish_reason=result.finish_reason,
                context_truncated=truncated,
                sources_in_prompt=n_in_prompt,
            ),
            cancelled=result.cancelled,
        )

    def answer(
        self,
        question: str,
        document_ids: list[str],
        k: Optional[int] = None,
        on_retrieved: Optional[Callable[[list[RetrievedChunk], float], None]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        history: Optional[list[tuple[str, str]]] = None,
    ) -> ChatResponse:
        k = self.resolve_k(k)
        self.check_documents(document_ids)
        retrieval = self.retrieve(question, document_ids, k)
        if on_retrieved:
            on_retrieved(retrieval.chunks, retrieval.retrieval_ms)
        return self.answer_from_sources(
            question, retrieval.chunks, k, retrieval.retrieval_ms, on_token, should_stop, history
        )

    def answer_without_context(self, question: str) -> GenerationResult:
        """No-RAG baseline (research only): same model and generation parameters, no sources."""
        return self.llm.generate(build_no_rag_messages(question), self.params)
