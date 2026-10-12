import json

import numpy as np
import pytest

from backend.app.schemas import Chunk
from backend.app.services.retrieval_service import EmptyIndexError, IndexIntegrityError, RetrievalService
from backend.app.storage.document_files import DocumentFiles

from .conftest import FakeEmbedder

DOC_A = "a" * 16
DOC_B = "b" * 16


def make_chunks(doc_id: str, texts: list[str]) -> list[Chunk]:
    return [
        Chunk(chunk_id=f"{doc_id}-c{i:04d}", document_id=doc_id, document_name=f"{doc_id[:1]}.pdf", index=i,
              pages=[i + 1], text=t, word_count=len(t.split()))
        for i, t in enumerate(texts)
    ]


@pytest.fixture
def service(tmp_path):
    embedder = FakeEmbedder()
    svc = RetrievalService(tmp_path, embedder)
    for doc_id, texts in {
        DOC_A: ["tuition fee payment schedule", "hostel room allotment rules", "library opening hours"],
        DOC_B: ["fee refund policy for withdrawal", "sports complex timings"],
    }.items():
        DocumentFiles(tmp_path, doc_id).create()
        chunks = make_chunks(doc_id, texts)
        svc.build_index(doc_id, chunks, embedder.encode([c.text for c in chunks]))
    return svc


def test_ranks_most_similar_first(service):
    res = service.retrieve("hostel room allotment", [DOC_A], k=3)
    assert res.chunks[0].text == "hostel room allotment rules"
    assert [c.rank for c in res.chunks] == [1, 2, 3]
    assert [c.source_label for c in res.chunks] == ["S1", "S2", "S3"]
    sims = [c.similarity for c in res.chunks]
    assert sims == sorted(sims, reverse=True)
    assert -1.0 <= sims[-1] <= sims[0] <= 1.0
    assert res.retrieval_ms >= 0


def test_metadata_stays_aligned_with_vectors(service, tmp_path):
    files = DocumentFiles(tmp_path, DOC_A)
    meta = json.loads(files.index_meta.read_text())
    stored = [json.loads(line)["chunk_id"] for line in files.chunks.read_text().splitlines()]
    assert meta["chunk_ids"] == stored
    assert np.load(files.embeddings).shape[0] == len(stored)
    for c in service.retrieve("library opening hours", [DOC_A], k=3).chunks:
        assert c.chunk_id.startswith(DOC_A) and c.pages == [int(c.chunk_id[-4:]) + 1]


def test_filters_by_document(service):
    only_b = service.retrieve("fee", [DOC_B], k=10)
    assert {c.document_id for c in only_b.chunks} == {DOC_B}
    both = service.retrieve("fee", [DOC_A, DOC_B], k=10)
    assert {c.document_id for c in both.chunks} == {DOC_A, DOC_B}


def test_fewer_chunks_than_k(service):
    res = service.retrieve("anything", [DOC_B], k=10)
    assert len(res.chunks) == 2


def test_k_is_prefix_consistent(service):
    top10 = [c.chunk_id for c in service.retrieve("fee policy", [DOC_A, DOC_B], k=10).chunks]
    for k in (1, 3, 5):
        assert [c.chunk_id for c in service.retrieve("fee policy", [DOC_A, DOC_B], k=k).chunks] == top10[:k]


def test_empty_index_raises(tmp_path):
    embedder = FakeEmbedder()
    svc = RetrievalService(tmp_path, embedder)
    DocumentFiles(tmp_path, DOC_A).create()
    svc.build_index(DOC_A, [], embedder.encode([]))
    with pytest.raises(EmptyIndexError):
        svc.retrieve("q", [DOC_A], k=3)


def test_missing_index_raises(tmp_path):
    svc = RetrievalService(tmp_path, FakeEmbedder())
    with pytest.raises(IndexIntegrityError):
        svc.retrieve("q", [DOC_A], k=3)


def test_detects_misaligned_metadata(service, tmp_path):
    files = DocumentFiles(tmp_path, DOC_A)
    lines = files.chunks.read_text().splitlines()
    files.chunks.write_text("\n".join(lines[:-1]) + "\n")
    service.evict(DOC_A)
    with pytest.raises(IndexIntegrityError):
        service.retrieve("q", [DOC_A], k=1)


def test_detects_embedding_model_change(service):
    service.embedder.model_name = "another-model"
    service.evict(DOC_A)
    with pytest.raises(IndexIntegrityError):
        service.retrieve("q", [DOC_A], k=1)
    service.embedder.model_name = FakeEmbedder.model_name
