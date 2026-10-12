import pytest

from backend.app.schemas import PageRecord
from backend.app.services.chunking_service import chunk_pages

from .conftest import words

DOC = "0123456789abcdef"


def page(n: int, paragraphs: list[str]) -> PageRecord:
    text = "\n\n".join(paragraphs)
    wc = len(text.split())
    return PageRecord(document_id=DOC, document_name="d.pdf", page=n, text=text, paragraphs=paragraphs,
                      word_count=wc, has_text=wc >= 5)


def test_chunks_respect_size_and_carry_metadata():
    pages = [page(1, [words("a", 60), words("b", 60)]), page(2, [words("c", 60), words("d", 60)])]
    chunks = chunk_pages(pages, chunk_size=130, overlap=20)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.word_count <= 130
        assert c.document_id == DOC and c.document_name == "d.pdf"
        assert c.pages and all(p in (1, 2) for p in c.pages)
        assert c.word_count == len(c.text.split())


def test_chunk_spanning_pages_lists_all_pages():
    pages = [page(1, [words("a", 40)]), page(2, [words("b", 40)])]
    chunks = chunk_pages(pages, chunk_size=200, overlap=20)
    assert len(chunks) == 1
    assert chunks[0].pages == [1, 2]
    # page_starts lets citations point at the right page inside the chunk
    assert [p for _, p in chunks[0].page_starts] == [1, 2]
    offset_page2 = chunks[0].page_starts[1][0]
    assert chunks[0].text[offset_page2:].startswith("b0")


def test_consecutive_chunks_overlap():
    pages = [page(1, [words("p", 50), words("q", 50), words("r", 50), words("s", 50)])]
    chunks = chunk_pages(pages, chunk_size=110, overlap=50)
    assert len(chunks) >= 2
    for prev, nxt in zip(chunks, chunks[1:]):
        prev_words, next_words = prev.text.split(), nxt.text.split()
        shared = set(prev_words[-50:]) & set(next_words[:50])
        assert shared, "expected overlapping words between consecutive chunks"


def test_word_level_overlap_when_paragraph_exceeds_overlap():
    pages = [page(1, [words("x", 100), words("y", 100)])]
    chunks = chunk_pages(pages, chunk_size=120, overlap=10)
    assert chunks[1].text.split()[:10] == words("x", 100).split()[-10:]


def test_empty_pages_are_skipped():
    pages = [page(1, [words("a", 30)]), page(2, []), page(3, [words("c", 30)])]
    chunks = chunk_pages(pages, chunk_size=500, overlap=50)
    assert all(2 not in c.pages for c in chunks)
    assert chunk_pages([page(1, [])], chunk_size=100, overlap=10) == []


def test_ids_are_stable_and_unique():
    pages = [page(1, [words("a", 300)]), page(2, [words("b", 300)])]
    first = chunk_pages(pages, chunk_size=120, overlap=20)
    second = chunk_pages(pages, chunk_size=120, overlap=20)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len({c.chunk_id for c in first}) == len(first)
    assert all(c.chunk_id.startswith(DOC) for c in first)


def test_long_paragraph_is_split():
    pages = [page(1, [words("w", 1000)])]
    chunks = chunk_pages(pages, chunk_size=200, overlap=20)
    assert all(c.word_count <= 200 for c in chunks)
    covered = set()
    for c in chunks:
        covered.update(c.text.split())
    assert covered == set(words("w", 1000).split())


def test_invalid_settings():
    with pytest.raises(ValueError):
        chunk_pages([page(1, ["a b c d e"])], chunk_size=50, overlap=50)
