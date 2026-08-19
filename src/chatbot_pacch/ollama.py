from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def health(self) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                version_response = await client.get(f"{self.base_url}/api/version")
                version_response.raise_for_status()
                tags_response = await client.get(f"{self.base_url}/api/tags")
                tags_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"No se pudo conectar con Ollama: {exc}") from exc

        models = [model.get("name", "") for model in tags_response.json().get("models", [])]
        return {"version": version_response.json().get("version"), "models": models}

    async def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": model, "input": inputs, "keep_alive": "2m"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama no pudo generar embeddings: {exc}") from exc
        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
            raise OllamaError("Ollama devolvio una respuesta de embeddings invalida")
        return embeddings

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "2m",
            "options": {
                "temperature": 0.2,
                "num_predict": 140,
                "num_ctx": 4096,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Ollama no pudo generar la respuesta: {exc}") from exc
