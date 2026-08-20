from __future__ import annotations

import asyncio
import json
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from chatbot_pacch.config import get_settings
from chatbot_pacch.database import Database
from chatbot_pacch.ollama import OllamaClient, OllamaError
from chatbot_pacch.rag.answer import build_messages, public_source_url, public_sources
from chatbot_pacch.rag.retrieval import HybridRetriever, has_sufficient_evidence


settings = get_settings()
database = Database(settings.database_path)
database.initialize()
retriever = HybridRetriever(settings, database)
generation_slot = asyncio.Semaphore(1)
package_dir = Path(__file__).resolve().parent
app = FastAPI(
    title="Chatbot PACCH",
    version="0.1.0",
    root_path=settings.root_path,
)
app.mount("/static", StaticFiles(directory=package_dir / "static"), name="static")


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Escribe una pregunta mas completa")
        return value


def _event(event_type: str, **payload: object) -> bytes:
    return (
        json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"
    ).encode("utf-8")


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(package_dir / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, object]:
    ollama = OllamaClient(settings.ollama_base_url)
    try:
        ollama_status: dict[str, object] = await ollama.health()
        ollama_ok = True
    except OllamaError as exc:
        ollama_status = {"error": str(exc)}
        ollama_ok = False

    return {
        "status": "ok" if ollama_ok else "degraded",
        "database": database.corpus_stats(),
        "ollama": ollama_status,
        "required_models": {
            "chat": settings.ollama_chat_model,
            "embedding": settings.ollama_embedding_model,
        },
    }


@app.get("/api/corpus")
async def corpus() -> dict[str, int]:
    return database.corpus_stats()


@app.get("/api/subjects")
async def indexed_subjects() -> dict[str, list[str]]:
    return {"subjects": database.indexed_subjects()}


@app.post("/api/search")
async def search(payload: QueryRequest) -> dict[str, object]:
    results = await retriever.search(payload.question, 6)
    return {
        "sufficient": has_sufficient_evidence(results),
        "results": [
            {
                "title": result.title,
                "heading": result.heading,
                "subject": result.subject,
                "url": public_source_url(result.url),
                "excerpt": result.text[:280],
                "semantic_score": result.semantic_score,
            }
            for result in results
        ],
    }


@app.post("/api/chat")
async def chat(payload: QueryRequest, request: Request) -> StreamingResponse:
    async def stream() -> AsyncIterator[bytes]:
        try:
            results = await retriever.search(payload.question, 3)
            sources = public_sources(results)
            yield _event("sources", sources=sources)
            if not has_sufficient_evidence(results):
                yield _event(
                    "token",
                    content=(
                        "No encontré información suficiente en los recursos "
                        "indexados para responder con seguridad. Intenta usar "
                        "otro concepto o revisa las fuentes sugeridas."
                    ),
                )
                yield _event("done", refused=True)
                return

            async with generation_slot:
                ollama = OllamaClient(settings.ollama_base_url)
                async for token in ollama.chat_stream(
                    settings.ollama_chat_model,
                    build_messages(payload.question, results),
                ):
                    if await request.is_disconnected():
                        return
                    yield _event("token", content=token)
            yield _event("done", refused=False)
        except (OllamaError, ValueError) as exc:
            yield _event("error", message=str(exc))

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
