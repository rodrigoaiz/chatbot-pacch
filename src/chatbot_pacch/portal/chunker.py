from __future__ import annotations

from chatbot_pacch.models import Chunk, ExtractedDocument


def _split_long_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    parts: list[str] = []
    remaining = block
    while len(remaining) > max_chars:
        split_at = remaining.rfind(". ", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = remaining.rfind(" ", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        parts.append(remaining[: split_at + 1].strip())
        remaining = remaining[split_at + 1 :].strip()
    if remaining:
        parts.append(remaining)
    return parts


def chunk_document(
    document: ExtractedDocument,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    ordinal = 0

    for section in document.sections:
        current: list[str] = []
        current_length = 0
        previous_tail = ""

        def flush() -> None:
            nonlocal ordinal, current, current_length, previous_tail
            if not current:
                return
            text = "\n\n".join(current).strip()
            chunks.append(Chunk(ordinal=ordinal, heading=section.heading, text=text))
            ordinal += 1
            previous_tail = text[-overlap_chars:].lstrip() if overlap_chars else ""
            if overlap_chars and len(text) > overlap_chars and " " in previous_tail:
                previous_tail = previous_tail.split(" ", 1)[1]
            current = []
            current_length = 0

        for original_block in section.blocks:
            for block in _split_long_block(original_block, max_chars):
                added_length = len(block) + (2 if current else 0)
                if current and current_length + added_length > max_chars:
                    flush()
                    if previous_tail and previous_tail != block:
                        current.append(previous_tail)
                        current_length = len(previous_tail)
                current.append(block)
                current_length += len(block) + (2 if len(current) > 1 else 0)
        flush()
    return chunks
