from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from chatbot_pacch.config import Settings
from chatbot_pacch.database import Database
from chatbot_pacch.models import IngestionStats
from chatbot_pacch.portal.chunker import chunk_document
from chatbot_pacch.portal.crawler import PortalClient
from chatbot_pacch.portal.discovery import discover_pages
from chatbot_pacch.portal.extractor import extract_document


MIN_FREE_DISK_BYTES = 8 * 1024**3
PROCESSOR_VERSION = "1"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_disk(path: Path) -> None:
    existing_parent = path.parent
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    free = shutil.disk_usage(existing_parent).free
    if free < MIN_FREE_DISK_BYTES:
        raise RuntimeError(
            "La ingestion se detuvo porque quedan menos de 8 GB libres en disco"
        )


async def run_ingestion(
    settings: Settings,
    *,
    subject: str | None = None,
    index_all_objects: bool | None = None,
    max_pages: int | None = None,
) -> IngestionStats:
    database = Database(settings.database_path)
    database.initialize()
    stats = IngestionStats()
    run_id = database.start_run()

    selected_subject = subject or settings.subject
    selected_all = (
        settings.index_all_objects
        if index_all_objects is None
        else index_all_objects
    )
    selected_limit = max_pages or settings.max_pages

    try:
        _check_disk(settings.database_path)
        async with PortalClient(
            settings.portal_base_url,
            settings.user_agent,
            settings.request_delay_seconds,
            settings.request_timeout_seconds,
        ) as client:
            pages = await discover_pages(
                client,
                base_url=settings.portal_base_url,
                subject_slug=selected_subject,
                index_all_objects=selected_all,
                max_pages=selected_limit,
            )
            stats.discovered = len(pages)

            for page in pages:
                _check_disk(settings.database_path)
                state = database.get_document_state(page.url)
                skip_state = database.get_skip_state(page.url)
                if (
                    state
                    and state.processor_version == PROCESSOR_VERSION
                    and page.lastmod
                    and state.lastmod == page.lastmod
                ):
                    stats.skipped += 1
                    continue
                if (
                    skip_state
                    and skip_state.processor_version == PROCESSOR_VERSION
                    and skip_state.lastmod == page.lastmod
                ):
                    stats.skipped += 1
                    continue
                try:
                    html = await client.get_text(page.url)
                    stats.fetched += 1
                    document = extract_document(html, page)
                    chunks = chunk_document(document)
                    if not chunks:
                        raise ValueError("No se generaron fragmentos")
                    content_hash = _content_hash(document.text)
                    if (
                        state
                        and state.processor_version == PROCESSOR_VERSION
                        and state.content_hash == content_hash
                    ):
                        database.touch_document(page.url, page.lastmod)
                        stats.unchanged += 1
                        continue
                    is_new = database.upsert_document(
                        document, chunks, content_hash, PROCESSOR_VERSION
                    )
                    if is_new:
                        stats.inserted += 1
                    else:
                        stats.updated += 1
                except ValueError as exc:
                    if "texto academico extraible" in str(exc) or "bloque principal" in str(exc):
                        database.record_skipped_page(
                            page.url,
                            page.lastmod,
                            str(exc),
                            PROCESSOR_VERSION,
                        )
                        stats.skipped += 1
                        continue
                    stats.failed += 1
                    stats.errors.append(f"{page.url}: {exc}")
                except Exception as exc:
                    stats.failed += 1
                    stats.errors.append(f"{page.url}: {exc}")

        status = "completed" if stats.failed == 0 else "completed_with_errors"
        database.finish_run(run_id, stats, status)
        return stats
    except Exception:
        database.finish_run(run_id, stats, "failed")
        raise
