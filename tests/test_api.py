import httpx
import pytest

import chatbot_pacch.main as main_module
from chatbot_pacch.models import SearchResult


app = main_module.app


@pytest.mark.asyncio
async def test_corpus_endpoint_is_available() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/api/corpus")
    assert response.status_code == 200
    assert set(response.json()) == {"documents", "chunks", "embedded_chunks"}


@pytest.mark.asyncio
async def test_subjects_endpoint_is_available() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/api/subjects")
    assert response.status_code == 200
    assert isinstance(response.json()["subjects"], list)


@pytest.mark.asyncio
async def test_chat_streams_sources_and_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SearchResult(
        chunk_id=1,
        title="Liberalismo político",
        subject="Historia Universal I",
        heading="Derechos naturales",
        text="La libertad, la vida y la propiedad son derechos naturales.",
        url="https://portalacademico.cch.unam.mx/recurso",
        score=0.03,
        semantic_score=0.6,
        lexical_rank=1,
    )

    class FakeRetriever:
        async def search(self, _query: str, _limit: int) -> list[SearchResult]:
            return [result]

    class FakeOllama:
        def __init__(self, _base_url: str) -> None:
            pass

        async def chat_stream(self, _model: str, _messages: object):
            yield "Respuesta [1]."

    monkeypatch.setattr(main_module, "retriever", FakeRetriever())
    monkeypatch.setattr(main_module, "OllamaClient", FakeOllama)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/chat", json={"question": "¿Qué son los derechos naturales?"}
        )

    events = [line for line in response.text.splitlines() if line]
    assert response.status_code == 200
    assert '"type": "sources"' in events[0]
    assert any('"type": "token"' in event for event in events)
    assert '"type": "done"' in events[-1]


@pytest.mark.asyncio
async def test_chat_does_not_emit_an_unsupported_streamed_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = SearchResult(
        chunk_id=1,
        title="Primera etapa: Inicio",
        subject="Historia de Mexico I",
        heading="Primera etapa: Inicio",
        text="El movimiento inicio el 16 de septiembre de 1810.",
        url="https://portalacademico.cch.unam.mx/recurso",
        score=0.03,
        semantic_score=0.6,
        lexical_rank=1,
    )

    class FakeRetriever:
        async def search(self, _query: str, _limit: int) -> list[SearchResult]:
            return [result]

    class FakeOllama:
        def __init__(self, _base_url: str) -> None:
            pass

        async def chat_stream(self, _model: str, _messages: object):
            yield "El movimiento inicio el 9 de "
            yield "septiembre de 1810 [1]."

    monkeypatch.setattr(main_module, "retriever", FakeRetriever())
    monkeypatch.setattr(main_module, "OllamaClient", FakeOllama)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"question": "¿Cual fue la fecha de inicio del movimiento?"},
        )

    assert "9 de septiembre" not in response.text
    assert "No pude verificar" in response.text
    assert '"refused": true' in response.text
