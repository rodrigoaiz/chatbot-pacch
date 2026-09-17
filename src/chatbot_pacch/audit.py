from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from chatbot_pacch.config import Settings
from chatbot_pacch.database import Database
from chatbot_pacch.portal.crawler import PortalClient
from chatbot_pacch.portal.discovery import discover_pages, parse_catalog, slugify
from chatbot_pacch.rag.answer import public_source_url


@dataclass(frozen=True, slots=True)
class AuditReport:
    catalog_objects: int
    catalog_subjects: int
    catalog_objects_with_sitemap_pages: int
    discovered_pages: int
    duplicate_discovered_urls: int
    indexed_pages: int
    skipped_pages: int
    missing_pages: tuple[str, ...]
    stale_indexed_pages: tuple[str, ...]
    catalog_objects_without_pages: tuple[str, ...]
    malformed_urls: tuple[str, ...]
    indexed_subjects: int
    documents: int
    chunks: int
    embedded_chunks: int
    complete: bool


def malformed_urls(urls: list[str], base_url: str) -> list[str]:
    base_host = urlsplit(base_url).netloc
    invalid: list[str] = []
    for url in urls:
        raw = urlsplit(url)
        public = urlsplit(public_source_url(url))
        if (
            raw.netloc != base_host
            or "//" in raw.path
            or public.netloc not in {base_host, "e1.portalacademico.cch.unam.mx"}
            or "//" in public.path
        ):
            invalid.append(url)
    return invalid


def _database_urls(database: Database) -> tuple[set[str], set[str]]:
    with database.connect() as connection:
        indexed = {
            row["url"]
            for row in connection.execute(
                "SELECT url FROM documents WHERE active = 1"
            ).fetchall()
        }
        skipped = {
            row["url"]
            for row in connection.execute("SELECT url FROM skipped_pages").fetchall()
        }
    return indexed, skipped


async def audit_catalog(
    settings: Settings,
    *,
    subject: str | None = None,
    index_all_objects: bool = False,
) -> AuditReport:
    database = Database(settings.database_path)
    database.initialize()
    async with PortalClient(
        settings.portal_base_url,
        settings.user_agent,
        settings.request_delay_seconds,
        settings.request_timeout_seconds,
    ) as client:
        catalog_html = await client.get_text(
            f"{settings.portal_base_url}/objetos-de-aprendizaje"
        )
        catalog = parse_catalog(catalog_html, settings.portal_base_url)
        pages = await discover_pages(
            client,
            base_url=settings.portal_base_url,
            subject_slug=slugify(subject or settings.subject),
            index_all_objects=index_all_objects,
            max_pages=10_000 if index_all_objects else settings.max_pages,
        )

    discovered_urls = [page.url for page in pages]
    discovered_set = set(discovered_urls)
    indexed, skipped = _database_urls(database)
    accounted = indexed | skipped
    roots = {page.object_root for page in pages}
    selected_subject = slugify(subject or settings.subject)
    selected_catalog = [
        item
        for item in catalog
        if index_all_objects or item.subject_slug == selected_subject
    ]
    stats = database.corpus_stats()
    missing = tuple(sorted(discovered_set - accounted))
    stale = tuple(sorted(indexed - discovered_set))
    without_pages = tuple(
        sorted(item.root_url for item in selected_catalog if item.root_url not in roots)
    )
    invalid = tuple(sorted(malformed_urls(discovered_urls, settings.portal_base_url)))
    indexed_subjects = len(database.indexed_subjects())

    return AuditReport(
        catalog_objects=len(selected_catalog),
        catalog_subjects=len({item.subject_slug for item in selected_catalog}),
        catalog_objects_with_sitemap_pages=len(roots),
        discovered_pages=len(discovered_set),
        duplicate_discovered_urls=len(discovered_urls) - len(discovered_set),
        indexed_pages=len(indexed & discovered_set),
        skipped_pages=len(skipped & discovered_set),
        missing_pages=missing,
        stale_indexed_pages=stale,
        catalog_objects_without_pages=without_pages,
        malformed_urls=invalid,
        indexed_subjects=indexed_subjects,
        documents=stats["documents"],
        chunks=stats["chunks"],
        embedded_chunks=stats["embedded_chunks"],
        complete=not missing and not without_pages and not invalid,
    )


def report_dict(report: AuditReport) -> dict[str, object]:
    return asdict(report)
