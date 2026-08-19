from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from chatbot_pacch.config import Settings
from chatbot_pacch.database import Database
from chatbot_pacch.ollama import OllamaClient


@dataclass(frozen=True, slots=True)
class EmbeddingStats:
    processed: int
    remaining: int


def embedding_text(title: str, subject: str, heading: str, text: str) -> str:
    return f"Asignatura: {subject}\nRecurso: {title}\nSeccion: {heading}\n{text}"


async def embed_pending_chunks(
    settings: Settings,
    *,
    limit: int | None = None,
    batch_size: int = 8,
) -> EmbeddingStats:
    database = Database(settings.database_path)
    database.initialize()
    pending = database.pending_embedding_chunks(settings.ollama_embedding_model, limit)
    ollama = OllamaClient(settings.ollama_base_url)
    processed = 0

    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        vectors = await ollama.embed(
            settings.ollama_embedding_model,
            [
                embedding_text(item.title, item.subject, item.heading, item.text)
                for item in batch
            ],
        )
        database.save_embeddings(
            settings.ollama_embedding_model,
            [
                (item.chunk_id, np.asarray(vector, dtype=np.float32).tobytes())
                for item, vector in zip(batch, vectors, strict=True)
            ],
        )
        processed += len(batch)

    remaining = len(
        database.pending_embedding_chunks(settings.ollama_embedding_model)
    )
    return EmbeddingStats(processed=processed, remaining=remaining)
