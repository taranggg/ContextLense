import pytest

from backend.app.config import Settings
from backend.app.schemas import RetrievedChunk
from backend.app.services.evaluation_service import check_claims, condition_metrics, score_accuracy
from backend.app.services.llm_service import DisabledBackend, LLMUnavailableError, MLXBackend, create_llm_backend
from backend.app.services.prompts import ABSTAIN_SENTENCE, build_rag_messages, is_abstention
from backend.app.services.rag_service import best_excerpt, build_citations, pages_for_span, parse_citation_labels


def src(rank: int, text: str, pages=None, page_starts=None) -> RetrievedChunk:
    return RetrievedChunk(rank=rank, source_label=f"S{rank}", chunk_id=f"c{rank}", document_id="d" * 16,
                          document_name="doc.pdf", pages=pages or [rank], text=text, word_count=len(text.split()),
                          page_starts=page_starts or [], similarity=0.9 - rank / 10)


def test_parse_citation_labels_variants():
    answer = "Fee is Rs 5000 [S1]. Hostels exist [S2, S3][S2]. See [s4; 5]. Not a cite [x]."
    assert parse_citation_labels(answer) == ["S1", "S2", "S3", "S4", "S5"]


def test_citations_come_from_retrieved_metadata_and_invalid_markers_are_flagged():
    sources = [src(1, "The application fee is Rs 5000."), src(2, "Hostel rooms are allotted on arrival.")]
    citations, invalid = build_citations("The fee is Rs 5000 [S1]. Something else [S7].", "fee?", sources)
    assert [c.source_label for c in citations] == ["S1"]
    c = citations[0]
    assert (c.chunk_id, c.document_name, c.pages, c.similarity) == ("c1", "doc.pdf", [1], sources[0].similarity)
    assert "Rs 5000" in c.excerpt
    assert invalid == ["S7"]


def test_excerpt_pages_follow_page_offsets():
    text = "Intro on page one.\n\nThe fee is Rs 5000 on page two."
    offset = text.index("The fee")
    s = src(1, text, pages=[1, 2], page_starts=[(0, 1), (offset, 2)])
    citations, _ = build_citations("Fee is Rs 5000 [S1].", "what is the fee", [s])
    assert citations[0].excerpt_pages in ([2], [1, 2])
    assert pages_for_span([(0, 1), (offset, 2)], offset, len(text), [1, 2]) == [2]
    assert pages_for_span([(0, 1), (offset, 2)], 0, 5, [1, 2]) == [1]


def test_best_excerpt_prefers_relevant_sentences():
    text = "Sports facilities are large. The library opens at 8 am. Mess food is served daily."
    excerpt, start, end = best_excerpt(text, "when does the library open")
    assert "library opens at 8 am" in excerpt
    assert text[start:end].startswith("The library") or start == 0


def test_abstention_detection():
    assert is_abstention(ABSTAIN_SENTENCE + " The sources cover fees.")
    assert is_abstention("I could not find enough information to answer.")
    assert not is_abstention("The fee is Rs 5000 [S1].")


def test_prompt_labels_sources_with_document_and_pages():
    messages = build_rag_messages("q?", [src(1, "alpha", pages=[3, 4])])
    assert "[S1] doc.pdf, pages 3–4\nalpha" in messages[1]["content"]
    assert "ONLY the provided document excerpts" in messages[0]["content"]
    assert "[S#]" in messages[0]["content"]


def test_accuracy_rubric():
    facts = ["Rs 5000", "application fee"]
    assert score_accuracy(facts, "The application fee is Rs 5,000 [S1].")["score"] == 2
    assert score_accuracy(facts, "The application fee is Rs 4000.")["score"] == 1
    assert score_accuracy(facts, ABSTAIN_SENTENCE)["score"] == 0


def test_claim_check_flags_numbers_missing_from_evidence():
    checks = check_claims("The application fee is Rs 7000 for all candidates.", "The application fee is Rs 5000 for all candidates.")
    assert checks[0].label == "unsupported" and checks[0].missing_numbers == ["7000"]
    ok = check_claims("The application fee is Rs 5000 for all candidates.", "The application fee is Rs 5000 for all candidates.")
    assert ok[0].label == "supported"


def test_condition_metrics_citation_validity():
    m = condition_metrics("Fee is Rs 5000 [S1]. Also [S9] says more things here.", "Fee is Rs 5000.", {"S1", "S2"})
    assert m.citation_count == 2 and m.invalid_citation_count == 1 and m.citation_validity == 0.5
    baseline = condition_metrics("Paris is the capital of France.", "", None)
    assert baseline.citation_validity is None and baseline.claims_total == 0


def test_disabled_runtime_raises_clear_error():
    llm = create_llm_backend(Settings(llm_runtime="none"))
    assert isinstance(llm, DisabledBackend)
    assert llm.status().status == "not_configured"
    with pytest.raises(LLMUnavailableError):
        llm.generate([{"role": "user", "content": "hi"}], None)


def test_missing_mlx_model_is_reported_not_faked():
    llm = MLXBackend("contextlens-test/definitely-not-a-real-model", allow_download=False)
    with pytest.raises(LLMUnavailableError) as e:
        llm.generate([{"role": "user", "content": "hi"}], None)
    assert e.value.code in ("llm_not_downloaded", "llm_unavailable")
    assert llm.status().status in ("not_downloaded", "unavailable")


def test_excerpt_uses_claim_when_marker_follows_full_stop():
    text = "Hostels are allotted on arrival. The institute was designated an IIT on September 21, 2001. Sports are popular."
    citations, _ = build_citations("It became an IIT on September 21, 2001. [S1]", "history", [src(1, text)])
    assert "September 21, 2001" in citations[0].excerpt
