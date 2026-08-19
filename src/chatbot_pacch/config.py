from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    subject: str
    index_all_objects: bool
    max_pages: int
    request_delay_seconds: float
    request_timeout_seconds: float
    user_agent: str
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embedding_model: str
    app_host: str
    app_port: int
    root_path: str
    portal_base_url: str = "https://portalacademico.cch.unam.mx"


def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    database_path = Path(os.getenv("PACCH_DATABASE_PATH", "data/pacch.sqlite3"))
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    return Settings(
        database_path=database_path,
        subject=os.getenv(
            "PACCH_SUBJECT", "historia-universal-moderna-y-contemporanea-i"
        ),
        index_all_objects=_as_bool(os.getenv("PACCH_INDEX_ALL_OBJECTS", "false")),
        max_pages=max(1, int(os.getenv("PACCH_MAX_PAGES", "300"))),
        request_delay_seconds=max(
            0.0, float(os.getenv("PACCH_REQUEST_DELAY_SECONDS", "0.75"))
        ),
        request_timeout_seconds=max(
            1.0, float(os.getenv("PACCH_REQUEST_TIMEOUT_SECONDS", "30"))
        ),
        user_agent=os.getenv(
            "PACCH_USER_AGENT",
            "ChatbotPACCH-MVP/0.1 (prototipo academico local)",
        ),
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ).rstrip("/"),
        ollama_chat_model=os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:1.5b"),
        ollama_embedding_model=os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "embeddinggemma"
        ),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8765")),
        root_path=os.getenv("ROOT_PATH", "").rstrip("/"),
    )
