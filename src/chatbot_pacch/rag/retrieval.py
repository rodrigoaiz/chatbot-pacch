from __future__ import annotations

import asyncio
from collections import defaultdict

import numpy as np

from chatbot_pacch.config import Settings
from chatbot_pacch.database import Database
from chatbot_pacch.models import SearchResult, StoredChunk
from chatbot_pacch.ollama import OllamaClient


class HybridRetriever:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database
        self._chunks: list[StoredChunk] = []
        self._matrix: np.ndarray | None = None
        self._cache_signature: tuple[int, int] | None = None
        self._lock = asyncio.Lock()

    def _load_index(self) -> None:
        rows = self.database.vector_chunks(self.settings.ollama_embedding_model)
        signature = (len(rows), rows[-1][0].chunk_id if rows else 0)
        if signature == self._cache_signature:
            return
        self._chunks = [row[0] for row in rows]
        if rows:
            vectors = [np.frombuffer(row[1], dtype=np.float32) for row in rows]
            dimensions = {vector.shape for vector in vectors}
            if len(dimensions) != 1:
                raise ValueError("El indice contiene embeddings con dimensiones distintas")
            matrix = np.vstack(vectors)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            self._matrix = matrix / np.maximum(norms, 1e-12)
        else:
            self._matrix = None
        self._cache_signature = signature

    async def search(self, query: str, limit: int = 4) -> list[SearchResult]:
        async with self._lock:
            self._load_index()
            if self._matrix is None or not self._chunks:
                return []
            vectors = await OllamaClient(self.settings.ollama_base_url).embed(
                self.settings.ollama_embedding_model, [query]
            )
            query_vector = np.asarray(vectors[0], dtype=np.float32)
            query_vector /= max(float(np.linalg.norm(query_vector)), 1e-12)
            semantic_scores = self._matrix @ query_vector

        semantic_count = min(20, len(self._chunks))
        semantic_indexes = np.argpartition(
            -semantic_scores, semantic_count - 1
        )[:semantic_count]
        semantic_indexes = semantic_indexes[
            np.argsort(-semantic_scores[semantic_indexes])
        ]
        lexical = dict(self.database.lexical_search(query, limit=20))
        combined: defaultdict[int, float] = defaultdict(float)
        semantic_by_id: dict[int, float] = {}

        for rank, index in enumerate(semantic_indexes, 1):
            chunk_id = self._chunks[int(index)].chunk_id
            combined[chunk_id] += 1.2 / (60 + rank)
            semantic_by_id[chunk_id] = float(semantic_scores[int(index)])
        for chunk_id, rank in lexical.items():
            combined[chunk_id] += 1.0 / (60 + rank)

        chunks_by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        for chunk_id, score in list(combined.items()):
            chunk = chunks_by_id.get(chunk_id)
            if chunk and any(
                marker in chunk.url.casefold()
                for marker in ("/ejercicio", "/actividad", "/bibliografia", "/creditos")
            ):
                combined[chunk_id] = score * 0.65
        ranked = sorted(combined, key=combined.get, reverse=True)
        results: list[SearchResult] = []
        per_url: defaultdict[str, int] = defaultdict(int)
        for chunk_id in ranked:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None or per_url[chunk.url] >= 2:
                continue
            per_url[chunk.url] += 1
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    subject=chunk.subject,
                    heading=chunk.heading,
                    text=chunk.text,
                    url=chunk.url,
                    score=combined[chunk_id],
                    semantic_score=semantic_by_id.get(chunk_id),
                    lexical_rank=lexical.get(chunk_id),
                )
            )
            if len(results) >= limit:
                break
        return results


def has_sufficient_evidence(results: list[SearchResult]) -> bool:
    if not results:
        return False
    supported_lexical_match = any(
        result.lexical_rank is not None
        and result.lexical_rank <= 5
        and (result.semantic_score or 0.0) >= 0.25
        for result in results
    )
    best_semantic = max(result.semantic_score or 0.0 for result in results)
    return supported_lexical_match or best_semantic >= 0.38
