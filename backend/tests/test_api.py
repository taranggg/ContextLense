import json

import pytest
from fastapi.testclient import TestClient

from backend.app.container import build_container
from backend.app.main import create_app
from backend.app.services.llm_service import DisabledBackend
from backend.app.storage.document_files import DocumentFiles

from .conftest import FakeEmbedder, FakeLLM, make_pdf, upload, wait_ready


def ready_doc(client, pdf) -> str:
    r = upload(client, pdf)
    assert r.status_code == 202, r.text
    doc = wait_ready(client, r.json()["id"])
    assert doc["status"] == "ready", doc
    return doc["id"]


def test_health_does_not_claim_model_state(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "service": "contextlens-api"}


def test_readiness_reports_components(client):
    body = client.get("/api/ready").json()
    assert body["llm"]["status"] == "ready" and body["llm"]["model"] == "fake-model"
    assert body["limits"]["max_upload_mb"] == 25


def test_upload_process_list_and_inspect(client, sample_pdf):
    doc_id = ready_doc(client, sample_pdf)
    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["filename"] == "handbook.pdf"
    assert doc["page_count"] == 3 and doc["pages_with_text"] == 3 and doc["chunk_count"] >= 1
    assert doc["embedding_model"] == "fake-hash-embedder"
    assert [d["id"] for d in client.get("/api/documents").json()["documents"]] == [doc_id]
    chunks = client.get(f"/api/documents/{doc_id}/chunks?limit=5").json()
    assert chunks["total"] == doc["chunk_count"]
    assert all(c["document_id"] == doc_id for c in chunks["chunks"])


def test_filename_is_never_used_as_a_path(client, sample_pdf, settings):
    r = upload(client, sample_pdf, name="../../etc/passwd.pdf")
    doc = wait_ready(client, r.json()["id"])
    assert doc["filename"] == "passwd.pdf"
    assert (settings.documents_dir / doc["id"] / "source.pdf").exists()


@pytest.mark.parametrize(
    "name,content,ctype,status,code",
    [
        ("notes.txt", b"%PDF-1.7 fake", "application/pdf", 415, "invalid_extension"),
        ("a.pdf", b"%PDF-1.7 fake", "image/png", 415, "invalid_mime_type"),
        ("a.pdf", b"plain text, not a pdf", "application/pdf", 400, "not_a_pdf"),
        ("a.pdf", b"%PDF-1.7\ngarbage", "application/pdf", 400, None),
    ],
)
def test_invalid_uploads_are_rejected(client, tmp_path, name, content, ctype, status, code):
    path = tmp_path / "upload.bin"
    path.write_bytes(content)
    r = upload(client, path, name=name, content_type=ctype)
    assert r.status_code == status, r.text
    if code:
        assert r.json()["error"]["code"] == code
    assert client.get("/api/documents").json()["documents"] == []


def test_upload_size_limit(settings, tmp_path):
    small = settings.with_overrides(max_upload_mb=1)
    container = build_container(small, embedder=FakeEmbedder(), llm=FakeLLM())
    with TestClient(create_app(container=container)) as client:
        big = tmp_path / "big.pdf"
        big.write_bytes(b"%PDF-1.7\n" + b"0" * (2 * 1024 * 1024))
        r = upload(client, big)
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "file_too_large"
        assert not any(small.documents_dir.iterdir())
    container.close()


def test_image_only_pdf_fails_with_ocr_message(client, tmp_path):
    scanned = make_pdf(tmp_path / "scan.pdf", ["", ""])
    doc = wait_ready(client, upload(client, scanned).json()["id"])
    assert doc["status"] == "failed" and doc["error_code"] == "no_text"
    assert "OCR is not implemented" in doc["error_message"]


def test_partially_scanned_pdf_warns(client, tmp_path):
    pdf = make_pdf(tmp_path / "mixed.pdf", ["Real text about admission fees and dates.", ""])
    doc = wait_ready(client, upload(client, pdf).json()["id"])
    assert doc["status"] == "ready"
    assert doc["warnings"] and "1 of 2 pages" in doc["warnings"][0]


def test_chat_returns_answer_with_citations(client, sample_pdf, fake_llm):
    doc_id = ready_doc(client, sample_pdf)
    r = client.post("/api/chat", json={"question": "What is the application fee?", "document_ids": [doc_id], "k": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "The fee is Rs 5000 [S1]."
    assert body["citations"][0]["source_label"] == "S1"
    s1 = body["retrieved"][0]
    assert body["citations"][0]["chunk_id"] == s1["chunk_id"] and body["citations"][0]["pages"] == s1["pages"]
    assert body["latency"]["total_ms"] >= body["latency"]["retrieval_ms"]
    assert body["model"]["model"] == "fake-model"
    messages, _ = fake_llm.calls[-1]
    assert "Question: What is the application fee?" in messages[1]["content"]


def test_chat_validation_errors(client, sample_pdf):
    assert client.post("/api/chat", json={"question": "  ", "document_ids": ["x"]}).status_code == 422
    assert client.post("/api/chat", json={"question": "q", "document_ids": []}).status_code == 422
    r = client.post("/api/chat", json={"question": "q", "document_ids": ["0" * 16]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "document_not_found"
    doc_id = ready_doc(client, sample_pdf)
    assert client.post("/api/chat", json={"question": "q", "document_ids": [doc_id], "k": 999}).status_code == 422


def test_chat_with_unavailable_model_returns_503_not_an_answer(settings, sample_pdf):
    llm = DisabledBackend("none", "none", "Local inference is disabled.")
    container = build_container(settings, embedder=FakeEmbedder(), llm=llm)
    with TestClient(create_app(container=container)) as client:
        doc_id = ready_doc(client, sample_pdf)
        r = client.post("/api/chat", json={"question": "fee?", "document_ids": [doc_id]})
        assert r.status_code == 503
        assert r.json() == {"error": {"code": "llm_not_configured", "message": "Local inference is disabled."}}
        assert client.get("/api/ready").json()["ready"] is False
    container.close()


def test_chat_stream_event_order(client, sample_pdf):
    doc_id = ready_doc(client, sample_pdf)
    with client.stream("POST", "/api/chat/stream", json={"question": "fee?", "document_ids": [doc_id], "k": 2}) as r:
        assert r.status_code == 200
        events = [line.split(": ", 1)[1] for line in r.iter_lines() if line.startswith("event: ")]
    assert events[0] == "retrieval" and events[-1] == "done" and "token" in events


def test_context_is_trimmed_to_budget(settings, sample_pdf):
    tight = settings.with_overrides(llm_context_tokens=500, llm_max_tokens=100, chunk_size_words=40, chunk_overlap_words=5)
    llm = FakeLLM()
    container = build_container(tight, embedder=FakeEmbedder(), llm=llm)
    long_pdf = make_pdf(sample_pdf.parent / "long.pdf", [" ".join(f"word{i}" for i in range(400))] * 3)
    with TestClient(create_app(container=container)) as client:
        doc_id = ready_doc(client, long_pdf)
        body = client.post("/api/chat", json={"question": "word5", "document_ids": [doc_id], "k": 10}).json()
        assert body["generation"]["context_truncated"] is True
        assert body["generation"]["sources_in_prompt"] < len(body["retrieved"])
        assert llm.count_tokens(llm.calls[-1][0]) <= 500 - 100 - 64
    container.close()


def test_delete_removes_everything(client, sample_pdf, settings):
    doc_id = ready_doc(client, sample_pdf)
    client.post("/api/research/compare", json={"question": "fee?", "document_ids": [doc_id], "k_values": [1]})
    assert client.get("/api/research/results").json()["comparisons"]
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert not DocumentFiles(settings.documents_dir, doc_id).dir.exists()
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get("/api/research/results").json()["comparisons"] == []
    r = client.post("/api/chat", json={"question": "fee?", "document_ids": [doc_id]})
    assert r.status_code == 409


def test_documents_persist_across_restart(settings, sample_pdf):
    c1 = build_container(settings, embedder=FakeEmbedder(), llm=FakeLLM())
    with TestClient(create_app(container=c1)) as client:
        doc_id = ready_doc(client, sample_pdf)
    c1.close()
    c2 = build_container(settings, embedder=FakeEmbedder(), llm=FakeLLM())
    with TestClient(create_app(container=c2)) as client:
        assert client.get(f"/api/documents/{doc_id}").json()["status"] == "ready"
        assert client.post("/api/chat", json={"question": "fee?", "document_ids": [doc_id]}).status_code == 200
    c2.close()


def test_research_compare_uses_identical_settings_across_k(client, sample_pdf, fake_llm):
    doc_id = ready_doc(client, sample_pdf)
    r = client.post("/api/research/compare", json={"question": "What is the fee?", "document_ids": [doc_id]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["condition"] for c in body["conditions"]] == ["k=1", "k=3", "k=5", "k=10"]
    assert body["evaluation_status"] == "not_evaluated"
    calls = fake_llm.calls[-4:]
    assert len({json.dumps(c[1].__dict__) for c in calls}) == 1, "generation params must not change with K"
    assert len({c[0][0]["content"] for c in calls}) == 1, "system prompt must not change with K"
    assert all("Question: What is the fee?" in c[0][1]["content"] for c in calls)
    ids = [[x["chunk_id"] for x in c["retrieved"]] for c in body["conditions"]]
    for shorter, longer in zip(ids, ids[1:]):
        assert longer[: len(shorter)] == shorter  # same index and ranking; only depth changes
    for cond in body["conditions"]:
        assert cond["metrics"]["citation_count"] == 1
    saved = client.get(f"/api/research/comparisons/{body['id']}").json()
    assert saved["question"] == "What is the fee?"
    results = client.get("/api/research/results").json()
    assert results["comparisons"][0]["id"] == body["id"]
    assert results["benchmark_runs"] == []


def test_research_no_rag_baseline_has_no_retrieval(client, sample_pdf, fake_llm):
    doc_id = ready_doc(client, sample_pdf)
    body = client.post(
        "/api/research/compare",
        json={"question": "fee?", "document_ids": [doc_id], "k_values": [1], "include_no_rag": True},
    ).json()
    baseline = body["conditions"][0]
    assert baseline["condition"] == "no_rag" and baseline["retrieved"] == []
    assert baseline["metrics"]["citation_validity"] is None
