from __future__ import annotations

import re
import unicodedata

from chatbot_pacch.models import SearchResult
from chatbot_pacch.rag.retrieval import FULL_DATE_RE


CITATION_RE = re.compile(r"\[\d+\]")
RANGE_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*[-–—]\s*\d+(?:[.,]\d+)?\b")
PERCENT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*%")
CENTURY_RE = re.compile(r"\bsiglo\s+[ivxlcdm]+\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[–—]", "-", value)
    value = re.sub(r"\s*%", "%", value)
    return " ".join(value.split())


def unsupported_precise_claims(
    answer: str, results: list[SearchResult]
) -> tuple[str, ...]:
    """Return dates and numeric claims that do not occur in the supplied sources."""
    source = _normalize(
        "\n".join(
            f"{result.title}\n{result.heading}\n{result.text}" for result in results
        )
    )
    answer_without_citations = CITATION_RE.sub("", answer)
    claims: list[str] = []
    for pattern in (FULL_DATE_RE, RANGE_RE, PERCENT_RE, CENTURY_RE, NUMBER_RE):
        claims.extend(match.group(0) for match in pattern.finditer(answer_without_citations))

    unsupported: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        normalized = _normalize(claim)
        if normalized not in source and normalized not in seen:
            seen.add(normalized)
            unsupported.append(claim)
    return tuple(unsupported)
