"""
On-disk layout for one document. Everything derived from a document lives in
its own directory, so deleting the directory removes all of it.

    <DATA_DIR>/documents/<document_id>/
        source.pdf        original upload (stored under a generated name)
        pages.jsonl       extracted page records
        chunks.jsonl      chunks, in FAISS row order
        embeddings.npy    float32 chunk vectors (L2-normalised)
        index.faiss       FAISS IndexFlatIP over embeddings.npy
        index_meta.json   embedding model, dimension, chunk-id order
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterable, Type, TypeVar

from pydantic import BaseModel

_DOC_ID_RE = re.compile(r"^[a-f0-9]{16}$")

M = TypeVar("M", bound=BaseModel)


def is_valid_document_id(doc_id: str) -> bool:
    return bool(_DOC_ID_RE.match(doc_id))


class DocumentFiles:
    def __init__(self, documents_dir: Path, doc_id: str):
        if not is_valid_document_id(doc_id):
            raise ValueError("Invalid document id")
        self.dir = documents_dir / doc_id
        self.source_pdf = self.dir / "source.pdf"
        self.pages = self.dir / "pages.jsonl"
        self.chunks = self.dir / "chunks.jsonl"
        self.embeddings = self.dir / "embeddings.npy"
        self.index = self.dir / "index.faiss"
        self.index_meta = self.dir / "index_meta.json"

    def create(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def remove_all(self) -> None:
        if self.dir.exists():
            shutil.rmtree(self.dir)

    def clear_derived(self) -> None:
        for path in (self.pages, self.chunks, self.embeddings, self.index, self.index_meta):
            path.unlink(missing_ok=True)


def write_jsonl(path: Path, items: Iterable[BaseModel]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")
    tmp.replace(path)


def read_jsonl(path: Path, model: Type[M]) -> list[M]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f if line.strip()]


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
