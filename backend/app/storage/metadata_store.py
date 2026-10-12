"""
Persistent metadata for documents and research comparisons (PostgreSQL).

Large derived artifacts (pages, chunks, vectors) live as files under
`<DATA_DIR>/documents/<document_id>/`; this store only holds metadata and
processing status so that everything survives a backend restart.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from ..schemas import DocumentInfo, DocumentStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    seq BIGSERIAL,
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    is_sample BOOLEAN NOT NULL DEFAULT FALSE,
    size_bytes BIGINT NOT NULL,
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
    seq BIGSERIAL,
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    document_ids TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    seq BIGSERIAL,
    key TEXT PRIMARY KEY,
    document_ids TEXT NOT NULL,
    title TEXT NOT NULL,
    turns TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    def __init__(self, database_url: str, schema: Optional[str] = None):
        self.database_url = database_url
        self.schema = schema
        self._lock = threading.Lock()
        self._conn = psycopg.connect(database_url, autocommit=False, row_factory=dict_row)
        with self._lock:
            if schema:
                self._conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
                self._conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            self._conn.execute(_SCHEMA)
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
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (doc_id, filename, DocumentStatus.queued.value, is_sample, size_bytes, ts, ts),
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
        fields["updated_at"] = now_iso()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        with self._lock:
            self._conn.execute(f"UPDATE documents SET {assignments} WHERE id = %s", (*fields.values(), doc_id))
            self._conn.commit()

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM documents WHERE id = %s", (doc_id,)).fetchone()
        return _row_to_doc(row) if row else None

    def list_documents(self) -> list[DocumentInfo]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM documents ORDER BY created_at DESC, seq DESC").fetchall()
        return [_row_to_doc(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def mark_interrupted(self) -> int:
        """Documents left mid-processing by a previous process cannot resume; mark them failed."""
        in_progress = [s.value for s in DocumentStatus if s not in (DocumentStatus.ready, DocumentStatus.failed)]
        placeholders = ",".join("%s" for _ in in_progress)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE documents SET status = %s, error_code = %s, error_message = %s, updated_at = %s "
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
                "INSERT INTO comparisons (id, created_at, question, document_ids, payload) VALUES (%s, %s, %s, %s, %s)",
                (comparison_id, created_at, question, json.dumps(document_ids), json.dumps(payload)),
            )
            self._conn.commit()

    def list_comparisons(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM comparisons ORDER BY created_at DESC, seq DESC LIMIT %s", (limit,)
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def get_comparison(self, comparison_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM comparisons WHERE id = %s", (comparison_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete_comparisons_for_document(self, doc_id: str) -> int:
        """Comparisons embed excerpts of the documents they used, so they go when a document goes."""
        with self._lock:
            rows = self._conn.execute("SELECT id, document_ids FROM comparisons").fetchall()
            ids = [r["id"] for r in rows if doc_id in json.loads(r["document_ids"])]
            for cid in ids:
                self._conn.execute("DELETE FROM comparisons WHERE id = %s", (cid,))
            self._conn.commit()
        return len(ids)

    # ------------------------------------------------------------------ conversations

    @staticmethod
    def _conv_key(document_ids: list[str]) -> str:
        """One conversation per exact set of documents searched together, regardless of order."""
        return ",".join(sorted(set(document_ids)))

    def append_turn(self, document_ids: list[str], turn: dict) -> None:
        key = self._conv_key(document_ids)
        ts = now_iso()
        with self._lock:
            row = self._conn.execute("SELECT turns FROM conversations WHERE key = %s", (key,)).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO conversations (key, document_ids, title, turns, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (key, json.dumps(sorted(set(document_ids))), turn["question"][:120], json.dumps([turn]), ts, ts),
                )
            else:
                turns = json.loads(row["turns"]) + [turn]
                self._conn.execute(
                    "UPDATE conversations SET turns = %s, updated_at = %s WHERE key = %s",
                    (json.dumps(turns), ts, key),
                )
            self._conn.commit()

    def get_conversation(self, document_ids: list[str]) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE key = %s", (self._conv_key(document_ids),)
            ).fetchone()
        return _row_to_conversation(row) if row else None

    def list_conversations(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC, seq DESC").fetchall()
        return [_row_to_conversation(r) for r in rows]

    def delete_conversation(self, document_ids: list[str]) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM conversations WHERE key = %s", (self._conv_key(document_ids),))
            self._conn.commit()
            return cur.rowcount > 0

    def delete_conversations_for_document(self, doc_id: str) -> int:
        with self._lock:
            rows = self._conn.execute("SELECT key, document_ids FROM conversations").fetchall()
            keys = [r["key"] for r in rows if doc_id in json.loads(r["document_ids"])]
            for key in keys:
                self._conn.execute("DELETE FROM conversations WHERE key = %s", (key,))
            self._conn.commit()
        return len(keys)


def _row_to_doc(row: dict) -> DocumentInfo:
    data = dict(row)
    data.pop("seq", None)
    data["warnings"] = json.loads(data.get("warnings") or "[]")
    return DocumentInfo(**data)


def _row_to_conversation(row: dict) -> dict:
    data = dict(row)
    data.pop("seq", None)
    data["document_ids"] = json.loads(data["document_ids"])
    data["turns"] = json.loads(data["turns"])
    return data
