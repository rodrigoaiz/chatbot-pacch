from __future__ import annotations

import asyncio
import time
import urllib.robotparser

import httpx


class PortalRequestError(RuntimeError):
    pass


class PortalClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        delay_seconds: float,
        timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self._last_request_at = 0.0
        self._request_lock = asyncio.Lock()
        self._robots: urllib.robotparser.RobotFileParser | None = None
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xml"},
        )

    async def __aenter__(self) -> PortalClient:
        await self.load_robots()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        async with self._request_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self.delay_seconds - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def _request(self, url: str, *, check_robots: bool = True) -> str:
        if check_robots and self._robots and not self._robots.can_fetch(
            self.user_agent, url
        ):
            raise PortalRequestError(f"robots.txt no permite consultar {url}")

        last_error: Exception | None = None
        for attempt in range(3):
            await self._throttle()
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        raise PortalRequestError(f"No se pudo descargar {url}: {last_error}")

    async def load_robots(self) -> None:
        robots_url = f"{self.base_url}/robots.txt"
        text = await self._request(robots_url, check_robots=False)
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(text.splitlines())
        self._robots = parser

    async def get_text(self, url: str) -> str:
        return await self._request(url)
