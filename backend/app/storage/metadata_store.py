"""
Persistent metadata for documents and research comparisons (SQLite).

Large derived artifacts (pages, chunks, vectors) live as files under
`<DATA_DIR>/documents/<document_id>/`; this store only holds metadata and
processing status so that everything survives a backend restart.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..schemas import DocumentInfo, DocumentStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    is_sample INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL,
    page_count INTEGER,
    pages_with_text INTEGER,
    chunk_count INTEGER,
    word_count INTEGER,
    embedding_model TEXT,
    chunk_size_words INTEGER,
    chunk_overlap_words INTEGER,
    error_code TEXT,
    error_message TEXT,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    document_ids TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

_DOC_COLUMNS = {
    "filename", "status", "is_sample", "size_bytes", "page_count", "pages_with_text", "chunk_count",
    "word_count", "embedding_model", "chunk_size_words", "chunk_overlap_words", "error_code",
    "error_message", "warnings",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MetadataStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ documents

    def create_document(self, doc_id: str, filename: str, size_bytes: int, is_sample: bool = False) -> DocumentInfo:
        ts = now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents (id, filename, status, is_sample, size_bytes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, filename, DocumentStatus.queued.value, int(is_sample), size_bytes, ts, ts),
            )
            self._conn.commit()
        doc = self.get_document(doc_id)
        assert doc is not None
        return doc

    def update_document(self, doc_id: str, **fields: Any) -> None:
        unknown = set(fields) - _DOC_COLUMNS
        if unknown:
            raise ValueError(f"Unknown document fields: {unknown}")
        if "status" in fields and isinstance(fields["status"], DocumentStatus):
            fields["status"] = fields["status"].value
        if "warnings" in fields:
            fields["warnings"] = json.dumps(fields["warnings"])
        if "is_sample" in fields:
            fields["is_sample"] = int(fields["is_sample"])
        fields["updated_at"] = now_iso()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._conn.execute(f"UPDATE documents SET {assignments} WHERE id = ?", (*fields.values(), doc_id))
            self._conn.commit()

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return _row_to_doc(row) if row else None

    def list_documents(self) -> list[DocumentInfo]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM documents ORDER BY created_at DESC, rowid DESC").fetchall()
        return [_row_to_doc(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def mark_interrupted(self) -> int:
        """Documents left mid-processing by a previous process cannot resume; mark them failed."""
        in_progress = [s.value for s in DocumentStatus if s not in (DocumentStatus.ready, DocumentStatus.failed)]
        placeholders = ",".join("?" for _ in in_progress)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE documents SET status = ?, error_code = ?, error_message = ?, updated_at = ? "
                f"WHERE status IN ({placeholders})",
                (
                    DocumentStatus.failed.value,
                    "interrupted",
                    "Processing was interrupted because the backend stopped. Retry processing to continue.",
                    now_iso(),
                    *in_progress,
                ),
            )
            self._conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------------ comparisons

    def save_comparison(self, comparison_id: str, created_at: str, question: str, document_ids: list[str], payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO comparisons (id, created_at, question, document_ids, payload) VALUES (?, ?, ?, ?, ?)",
                (comparison_id, created_at, question, json.dumps(document_ids), json.dumps(payload)),
            )
            self._conn.commit()

    def list_comparisons(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM comparisons ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def get_comparison(self, comparison_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete_comparisons_for_document(self, doc_id: str) -> int:
        """Comparisons embed excerpts of the documents they used, so they go when a document goes."""
        with self._lock:
            rows = self._conn.execute("SELECT id, document_ids FROM comparisons").fetchall()
            ids = [r["id"] for r in rows if doc_id in json.loads(r["document_ids"])]
            for cid in ids:
                self._conn.execute("DELETE FROM comparisons WHERE id = ?", (cid,))
            self._conn.commit()
        return len(ids)


def _row_to_doc(row: sqlite3.Row) -> DocumentInfo:
    data = dict(row)
    data["is_sample"] = bool(data["is_sample"])
    data["warnings"] = json.loads(data.get("warnings") or "[]")
    return DocumentInfo(**data)
