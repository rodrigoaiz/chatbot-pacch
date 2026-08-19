from pathlib import Path

import numpy as np

from chatbot_pacch.database import Database
from chatbot_pacch.models import Chunk, ExtractedDocument, Section


def _document(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        url="https://example.test/recurso",
        title="Recurso",
        subject="Historia",
        object_title="Objeto",
        lastmod="2026-01-01",
        sections=(Section(heading="Tema", blocks=(text,)),),
    )


def test_database_replaces_document_chunks(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    first = _document("Contenido inicial")
    assert database.upsert_document(
        first, [Chunk(0, "Tema", "Contenido inicial")], "hash-1", "1"
    )
    assert database.corpus_stats() == {
        "documents": 1,
        "chunks": 1,
        "embedded_chunks": 0,
    }

    second = _document("Contenido actualizado")
    assert not database.upsert_document(
        second,
        [
            Chunk(0, "Tema", "Contenido actualizado"),
            Chunk(1, "Tema", "Otro fragmento"),
        ],
        "hash-2",
        "1",
    )
    assert database.corpus_stats() == {
        "documents": 1,
        "chunks": 2,
        "embedded_chunks": 0,
    }
    assert database.get_document_state(second.url).content_hash == "hash-2"
    assert database.get_document_state(second.url).processor_version == "1"

    pending = database.pending_embedding_chunks("embeddinggemma")
    assert len(pending) == 2
    vector = np.asarray([0.1, 0.2, 0.3], dtype=np.float32).tobytes()
    database.save_embeddings("embeddinggemma", [(pending[0].chunk_id, vector)])
    assert database.corpus_stats()["embedded_chunks"] == 1
    assert len(database.vector_chunks("embeddinggemma")) == 1

    database.record_skipped_page(
        "https://example.test/vacio", "2026-01-01", "sin contenido", "1"
    )
    skip = database.get_skip_state("https://example.test/vacio")
    assert skip is not None
    assert skip.lastmod == "2026-01-01"
    assert skip.processor_version == "1"
