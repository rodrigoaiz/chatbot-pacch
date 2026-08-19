from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from chatbot_pacch.models import CatalogObject, DiscoveredPage, SitemapEntry
from chatbot_pacch.portal.crawler import PortalClient


IGNORED_SUFFIXES = (
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".svg",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def canonical_url(base_url: str, href: str) -> str | None:
    absolute = urljoin(f"{base_url.rstrip('/')}/", href)
    parts = urlsplit(absolute)
    base_parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or parts.netloc != base_parts.netloc:
        return None
    if parts.path.lower().endswith(IGNORED_SUFFIXES):
        return None
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((base_parts.scheme, base_parts.netloc, path, "", ""))


def parse_catalog(html: str, base_url: str) -> list[CatalogObject]:
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("main") or soup.select_one("#main-content") or soup
    current_subject = ""
    objects: dict[str, CatalogObject] = {}

    for element in main.select("h3, h4, h5"):
        if not isinstance(element, Tag):
            continue
        if element.name == "h3":
            current_subject = element.get_text(" ", strip=True)
            continue
        if not current_subject:
            continue
        anchor = element.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        url = canonical_url(base_url, str(anchor["href"]))
        title = anchor.get_text(" ", strip=True)
        if not url or not title:
            continue
        objects[url] = CatalogObject(
            root_url=url,
            title=title,
            subject=current_subject,
            subject_slug=slugify(current_subject),
        )
    return list(objects.values())


def parse_sitemap(xml: str) -> tuple[list[str], list[SitemapEntry]]:
    root = ET.fromstring(xml)
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    sitemap_urls = [
        loc.text.strip()
        for loc in root.findall(f"{namespace}sitemap/{namespace}loc")
        if loc.text
    ]
    entries: list[SitemapEntry] = []
    for node in root.findall(f"{namespace}url"):
        loc = node.find(f"{namespace}loc")
        lastmod = node.find(f"{namespace}lastmod")
        if loc is not None and loc.text:
            entries.append(
                SitemapEntry(
                    url=loc.text.strip(),
                    lastmod=lastmod.text.strip()
                    if lastmod is not None and lastmod.text
                    else None,
                )
            )
    return sitemap_urls, entries


def match_pages(
    objects: Iterable[CatalogObject],
    sitemap_entries: Iterable[SitemapEntry],
    *,
    subject_slug: str,
    index_all_objects: bool,
    max_pages: int,
) -> list[DiscoveredPage]:
    selected = [
        item
        for item in objects
        if index_all_objects or item.subject_slug == subject_slug
    ]
    entries = list(sitemap_entries)
    pages: dict[str, DiscoveredPage] = {}

    for item in selected:
        matching = [
            entry
            for entry in entries
            if entry.url == item.root_url
            or entry.url.startswith(f"{item.root_url}/")
        ]
        if not matching:
            matching = [SitemapEntry(item.root_url)]
        for entry in matching:
            pages.setdefault(
                entry.url,
                DiscoveredPage(
                    url=entry.url,
                    lastmod=entry.lastmod,
                    object_root=item.root_url,
                    object_title=item.title,
                    subject=item.subject,
                    subject_slug=item.subject_slug,
                ),
            )
            if len(pages) >= max_pages:
                return list(pages.values())
    return list(pages.values())


async def discover_pages(
    client: PortalClient,
    *,
    base_url: str,
    subject_slug: str,
    index_all_objects: bool,
    max_pages: int,
) -> list[DiscoveredPage]:
    catalog_html = await client.get_text(f"{base_url}/objetos-de-aprendizaje")
    objects = parse_catalog(catalog_html, base_url)
    if not objects:
        raise ValueError("No se encontraron objetos de aprendizaje en el catalogo")

    sitemap_index = await client.get_text(f"{base_url}/sitemap.xml")
    sitemap_urls, direct_entries = parse_sitemap(sitemap_index)
    entries = list(direct_entries)
    for sitemap_url in sitemap_urls:
        child_xml = await client.get_text(sitemap_url)
        _, child_entries = parse_sitemap(child_xml)
        entries.extend(child_entries)

    return match_pages(
        objects,
        entries,
        subject_slug=subject_slug,
        index_all_objects=index_all_objects,
        max_pages=max_pages,
    )
