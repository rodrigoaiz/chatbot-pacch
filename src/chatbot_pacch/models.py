from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CatalogObject:
    root_url: str
    title: str
    subject: str
    subject_slug: str


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    url: str
    lastmod: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredPage:
    url: str
    lastmod: str | None
    object_root: str
    object_title: str
    subject: str
    subject_slug: str


@dataclass(frozen=True, slots=True)
class Section:
    heading: str
    blocks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    url: str
    title: str
    subject: str
    object_title: str
    lastmod: str | None
    sections: tuple[Section, ...]
    citation: str | None = None

    @property
    def text(self) -> str:
        parts: list[str] = []
        for section in self.sections:
            if section.heading and section.heading != self.title:
                parts.append(section.heading)
            parts.extend(section.blocks)
        return "\n\n".join(parts)


@dataclass(frozen=True, slots=True)
class Chunk:
    ordinal: int
    heading: str
    text: str


@dataclass(slots=True)
class IngestionStats:
    discovered: int = 0
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StoredChunk:
    chunk_id: int
    title: str
    subject: str
    heading: str
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: int
    title: str
    subject: str
    heading: str
    text: str
    url: str
    score: float
    semantic_score: float | None = None
    lexical_rank: int | None = None
