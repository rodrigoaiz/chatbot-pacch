from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from chatbot_pacch.models import DiscoveredPage, ExtractedDocument, Section


REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "form",
    "aside",
    ".addtoany_list",
    ".book-navigation",
    ".breadcrumb",
    ".block-system-breadcrumb-block",
    ".social-media-sharing",
)

BOILERPLATE = {
    "cargando...",
    "leer mas",
    "menu",
    "pasar al contenido principal",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_useful(value: str) -> bool:
    normalized = value.casefold().strip(" .")
    return len(value) >= 2 and normalized not in BOILERPLATE


def _find_citation(soup: BeautifulSoup) -> str | None:
    text = soup.get_text("\n", strip=True)
    match = re.search(
        r"Como citar este objeto de aprendizaje\s*(.+?https?://\S+)",
        unicodedata_ascii(text),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return _clean_text(match.group(1))[:1000]


def unicodedata_ascii(value: str) -> str:
    # Citation detection only needs accent-insensitive matching; content stays intact.
    import unicodedata

    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def extract_document(html: str, page: DiscoveredPage) -> ExtractedDocument:
    soup = BeautifulSoup(html, "lxml")
    citation = _find_citation(soup)
    main = soup.select_one("main")
    if main is None:
        main_content = soup.select_one("#main-content")
        if isinstance(main_content, Tag) and main_content.name not in {"a", "span"}:
            main = main_content
    if main is None:
        page_heading = soup.find("h1")
        if isinstance(page_heading, Tag):
            main = page_heading.find_parent(["section", "article"])
    if main is None:
        raise ValueError("La pagina no contiene un bloque principal")

    for selector in REMOVE_SELECTORS:
        for element in main.select(selector):
            element.decompose()

    h1 = main.find("h1")
    title = _clean_text(h1.get_text(" ", strip=True)) if isinstance(h1, Tag) else ""
    if not title:
        title = page.object_title

    sections: list[Section] = []
    heading = title
    blocks: list[str] = []

    def flush() -> None:
        nonlocal blocks
        unique: list[str] = []
        for block in blocks:
            if block not in unique:
                unique.append(block)
        if unique and len(" ".join(unique)) >= 40:
            sections.append(Section(heading=heading, blocks=tuple(unique)))
        blocks = []

    for element in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]):
        if not isinstance(element, Tag):
            continue
        if element.name in {"h1", "h2", "h3", "h4"}:
            next_heading = _clean_text(element.get_text(" ", strip=True))
            if next_heading and next_heading != heading:
                flush()
                heading = next_heading
            continue
        if element.find_parent(["li", "table"]) is not None:
            continue
        value = _clean_text(element.get_text(" ", strip=True))
        if _is_useful(value):
            blocks.append(value)
    flush()

    if not sections:
        raise ValueError("La pagina no contiene texto academico extraible")

    return ExtractedDocument(
        url=page.url,
        title=title,
        subject=page.subject,
        object_title=page.object_title,
        lastmod=page.lastmod,
        sections=tuple(sections),
        citation=citation,
    )
