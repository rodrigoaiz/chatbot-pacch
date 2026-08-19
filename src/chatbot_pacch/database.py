from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from chatbot_pacch.models import Chunk, ExtractedDocument, StoredChunk


SEARCH_STOPWORDS = {
    "como",
    "cómo",
    "con",
    "cual",
    "cuál",
    "cuales",
    "cuáles",
    "del",
    "donde",
    "dónde",
    "el",
    "ella",
    "en",
    "esta",
    "este",
    "fue",
    "las",
    "los",
    "para",
    "por",
    "que",
    "qué",
    "quien",
    "quién",
    "segun",
    "según",
    "son",
    "una",
    "uno",
}


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    object_title TEXT NOT NULL,
    lastmod TEXT,
    citation TEXT,
    clean_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    processor_version TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB,
    embedding_model TEXT,
    UNIQUE(document_id, ordinal)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    title,
    subject,
    heading,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    fetched INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT
);

CREATE TABLE IF NOT EXISTS skipped_pages (
    url TEXT PRIMARY KEY,
    lastmod TEXT,
    reason TEXT NOT NULL,
    processor_version TEXT NOT NULL,
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_subject ON documents(subject);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
"""


@dataclass(frozen=True, slots=True)
class DocumentState:
    document_id: int
    lastmod: str | None
    content_hash: str
    processor_version: str


@dataclass(frozen=True, slots=True)
class SkipState:
    lastmod: str | None
    processor_version: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "processor_version" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN processor_version TEXT NOT NULL DEFAULT ''"
                )
            chunk_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(chunks)").fetchall()
            }
            if "embedding_model" not in chunk_columns:
                connection.execute("ALTER TABLE chunks ADD COLUMN embedding_model TEXT")

    def get_document_state(self, url: str) -> DocumentState | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, lastmod, content_hash, processor_version FROM documents WHERE url = ?",
                (url,),
            ).fetchone()
        if row is None:
            return None
        return DocumentState(
            row["id"], row["lastmod"], row["content_hash"], row["processor_version"]
        )

    def touch_document(self, url: str, lastmod: str | None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE documents SET lastmod = ?, fetched_at = ?, active = 1 WHERE url = ?",
                (lastmod, _now(), url),
            )

    def get_skip_state(self, url: str) -> SkipState | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT lastmod, processor_version FROM skipped_pages WHERE url = ?",
                (url,),
            ).fetchone()
        if row is None:
            return None
        return SkipState(row["lastmod"], row["processor_version"])

    def record_skipped_page(
        self,
        url: str,
        lastmod: str | None,
        reason: str,
        processor_version: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO skipped_pages (
                    url, lastmod, reason, processor_version, checked_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    lastmod = excluded.lastmod,
                    reason = excluded.reason,
                    processor_version = excluded.processor_version,
                    checked_at = excluded.checked_at
                """,
                (url, lastmod, reason, processor_version, _now()),
            )

    def upsert_document(
        self,
        document: ExtractedDocument,
        chunks: list[Chunk],
        content_hash: str,
        processor_version: str,
    ) -> bool:
        """Insert or replace a document. Returns True when it was newly inserted."""
        with self.connect() as connection:
            connection.execute("DELETE FROM skipped_pages WHERE url = ?", (document.url,))
            existing = connection.execute(
                "SELECT id FROM documents WHERE url = ?", (document.url,)
            ).fetchone()
            is_new = existing is None

            if is_new:
                cursor = connection.execute(
                    """
                    INSERT INTO documents (
                        url, title, subject, object_title, lastmod, citation,
                        clean_text, content_hash, processor_version, fetched_at, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        document.url,
                        document.title,
                        document.subject,
                        document.object_title,
                        document.lastmod,
                        document.citation,
                        document.text,
                        content_hash,
                        processor_version,
                        _now(),
                    ),
                )
                document_id = int(cursor.lastrowid)
            else:
                document_id = int(existing["id"])
                chunk_ids = connection.execute(
                    "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
                ).fetchall()
                if chunk_ids:
                    connection.executemany(
                        "DELETE FROM chunks_fts WHERE chunk_id = ?",
                        [(row["id"],) for row in chunk_ids],
                    )
                connection.execute(
                    "DELETE FROM chunks WHERE document_id = ?", (document_id,)
                )
                connection.execute(
                    """
                    UPDATE documents
                    SET title = ?, subject = ?, object_title = ?, lastmod = ?,
                        citation = ?, clean_text = ?, content_hash = ?,
                        processor_version = ?, fetched_at = ?, active = 1
                    WHERE id = ?
                    """,
                    (
                        document.title,
                        document.subject,
                        document.object_title,
                        document.lastmod,
                        document.citation,
                        document.text,
                        content_hash,
                        processor_version,
                        _now(),
                        document_id,
                    ),
                )

            for chunk in chunks:
                cursor = connection.execute(
                    """
                    INSERT INTO chunks (document_id, ordinal, heading, text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (document_id, chunk.ordinal, chunk.heading, chunk.text),
                )
                connection.execute(
                    """
                    INSERT INTO chunks_fts (chunk_id, title, subject, heading, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(cursor.lastrowid),
                        document.title,
                        document.subject,
                        chunk.heading,
                        chunk.text,
                    ),
                )
        return is_new

    def start_run(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO ingestion_runs (started_at, status) VALUES (?, 'running')",
                (_now(),),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, stats: object, status: str) -> None:
        errors = getattr(stats, "errors", [])
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET finished_at = ?, status = ?, discovered = ?, fetched = ?,
                    inserted = ?, updated = ?, unchanged = ?, skipped = ?,
                    failed = ?, error_summary = ?
                WHERE id = ?
                """,
                (
                    _now(),
                    status,
                    getattr(stats, "discovered", 0),
                    getattr(stats, "fetched", 0),
                    getattr(stats, "inserted", 0),
                    getattr(stats, "updated", 0),
                    getattr(stats, "unchanged", 0),
                    getattr(stats, "skipped", 0),
                    getattr(stats, "failed", 0),
                    "\n".join(errors[:20]) or None,
                    run_id,
                ),
            )

    def corpus_stats(self) -> dict[str, int]:
        self.initialize()
        with self.connect() as connection:
            documents = connection.execute(
                "SELECT COUNT(*) FROM documents WHERE active = 1"
            ).fetchone()[0]
            chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embedded = connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
            ).fetchone()[0]
        return {
            "documents": int(documents),
            "chunks": int(chunks),
            "embedded_chunks": int(embedded),
        }

    def indexed_subjects(self) -> list[str]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT subject
                FROM documents
                WHERE active = 1
                ORDER BY subject
                """
            ).fetchall()
        return [str(row["subject"]) for row in rows]

    def pending_embedding_chunks(
        self, model: str, limit: int | None = None
    ) -> list[StoredChunk]:
        sql = """
            SELECT c.id AS chunk_id, d.title, d.subject, c.heading, c.text, d.url
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.active = 1
              AND (c.embedding IS NULL OR c.embedding_model IS NOT ?)
            ORDER BY c.id
        """
        parameters: list[object] = [model]
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [StoredChunk(**dict(row)) for row in rows]

    def save_embeddings(self, model: str, values: list[tuple[int, bytes]]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "UPDATE chunks SET embedding = ?, embedding_model = ? WHERE id = ?",
                [(embedding, model, chunk_id) for chunk_id, embedding in values],
            )

    def vector_chunks(self, model: str) -> list[tuple[StoredChunk, bytes]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id AS chunk_id, d.title, d.subject, c.heading, c.text,
                       d.url, c.embedding
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.active = 1 AND c.embedding IS NOT NULL
                  AND c.embedding_model = ?
                ORDER BY c.id
                """,
                (model,),
            ).fetchall()
        return [
            (
                StoredChunk(
                    chunk_id=row["chunk_id"],
                    title=row["title"],
                    subject=row["subject"],
                    heading=row["heading"],
                    text=row["text"],
                    url=row["url"],
                ),
                row["embedding"],
            )
            for row in rows
        ]

    def lexical_search(self, query: str, limit: int = 20) -> list[tuple[int, int]]:
        tokens = [
            token.replace('"', '""')
            for token in re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)
            if len(token) >= 3 and token not in SEARCH_STOPWORDS
        ]
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens[:12])
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT CAST(chunk_id AS INTEGER) AS chunk_id
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts, 0.0, 2.0, 1.0, 1.5, 1.0)
                LIMIT ?
                """,
                (expression, limit),
            ).fetchall()
        return [(int(row["chunk_id"]), rank) for rank, row in enumerate(rows, 1)]
