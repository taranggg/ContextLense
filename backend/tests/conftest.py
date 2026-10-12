"""
Test fixtures. Tests never download or run a real model: the embedder is a
deterministic bag-of-words hash and the LLM is a scripted fake. The application
itself has no fake-answer path; these fakes exist only here.

Tests talk to the real Postgres from `docker compose up -d` (DATABASE_URL env
var, defaulting to the local dev instance); each test gets its own schema so
they don't interfere with each other or with data from the running app.
"""
from __future__ import annotations

import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import psycopg
import pymupdf
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from backend.app.config import Settings
from backend.app.container import build_container
from backend.app.main import create_app
from backend.app.schemas import LLMStatus
from backend.app.services.llm_service import GenerationParams, GenerationResult


class FakeEmbedder:
    model_name = "fake-hash-embedder"
    dim = 64

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)

    def status(self):
        return "ready", self.model_name


class FakeLLM:
    runtime = "fake"
    model_id = "fake-model"

    def __init__(self, reply: str | Callable[[list[dict]], str] = "The fee is Rs 5000 [S1]."):
        self.reply = reply
        self.calls: list[tuple[list[dict], GenerationParams]] = []

    def status(self) -> LLMStatus:
        return LLMStatus(status="ready", runtime=self.runtime, model=self.model_id)

    def start_loading(self) -> None:
        return None

    def count_tokens(self, messages: list[dict]) -> int:
        return sum(len(m["content"].split()) for m in messages)

    def generate(self, messages, params, on_token=None, should_stop=None) -> GenerationResult:
        self.calls.append((messages, params))
        text = self.reply(messages) if callable(self.reply) else self.reply
        for word in text.split(" "):
            if on_token:
                on_token(word + " ")
        return GenerationResult(text=text, prompt_tokens=self.count_tokens(messages), completion_tokens=len(text.split()),
                                finish_reason="stop", generation_ms=1.0)


def make_pdf(path: Path, pages: list[str], encrypt: bool = False) -> Path:
    """Write a PDF whose pages contain the given text ('' makes a page with no text layer)."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=9)
        else:
            page.draw_rect(pymupdf.Rect(100, 100, 300, 300), color=(0, 0, 0), fill=(0.5, 0.5, 0.5))
    kwargs = {}
    if encrypt:
        kwargs = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    doc.save(str(path), **kwargs)
    doc.close()
    return path


def words(prefix: str, n: int) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    schema = f"test_{uuid.uuid4().hex}"
    s = Settings(
        data_dir=tmp_path / "data",
        results_dir=tmp_path / "results",
        database_schema=schema,
        llm_preload=False,
        chunk_size_words=120,
        chunk_overlap_words=20,
        llm_context_tokens=100_000,
    )
    yield s
    with psycopg.connect(s.database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def container(settings, fake_llm):
    c = build_container(settings, embedder=FakeEmbedder(), llm=fake_llm)
    yield c
    c.close()


@pytest.fixture
def client(container):
    app = create_app(container=container)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return make_pdf(
        tmp_path / "handbook.pdf",
        [
            "Admissions\n\nThe application fee is Rs 5000 for all candidates. Applications close on 30 April.",
            "Hostel\n\nEvery student is allotted a hostel room. Mess charges are billed monthly.",
            "Library\n\nThe central library is open from 8 am to midnight on working days.",
        ],
    )


def wait_ready(client: TestClient, doc_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        doc = client.get(f"/api/documents/{doc_id}").json()
        if doc["status"] in ("ready", "failed"):
            return doc
        time.sleep(0.05)
    raise AssertionError(f"document {doc_id} did not finish processing")


def upload(client: TestClient, path: Path, name: Optional[str] = None, content_type: str = "application/pdf"):
    with open(path, "rb") as f:
        return client.post("/api/documents", files={"file": (name or path.name, f, content_type)})
