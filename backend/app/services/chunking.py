"""Page-aware chunking (docs/21_FILE_PROCESSING.md §7).

Chunks are built per page, splitting on paragraph boundaries and bounded by
a word budget with a sliding overlap, rather than chunking one flattened
blob for the whole document. This gives every chunk a real page number
(instead of a `(line // 45) + 1` guess) and carries OCR confidence with any
chunk that came from a recognized page, so retrieval/citation UI can label
uncertainty (RULE-10) instead of hiding it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.domain.models import FidelityTier
from app.services.parsing import ParsedDocument, ParsedPage

AnchorQuality = Literal["line", "paragraph", "cell", "bbox"]


@dataclass(slots=True)
class ChunkCandidate:
    page: int
    line_start: int
    line_end: int
    text: str
    ocr_confidence: float | None
    anchor_quality: AnchorQuality
    fidelity_tier: FidelityTier
    bbox: tuple[float, float, float, float] | None = None


def _paragraphs(text: str) -> list[tuple[int, int, str]]:
    """Split page text into (start_line, end_line, text) paragraphs, 1-indexed within the page."""
    lines = text.splitlines()
    paragraphs: list[tuple[int, int, str]] = []
    current: list[str] = []
    start = 1
    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append((start, index - 1, " ".join(current).strip()))
                current = []
            start = index + 1
            continue
        if not current:
            start = index
        current.append(line)
    if current:
        paragraphs.append((start, len(lines), " ".join(current).strip()))
    return [paragraph for paragraph in paragraphs if paragraph[2]]


def _chunk_page(
    page: ParsedPage,
    fidelity_tier: FidelityTier,
    anchor_quality: AnchorQuality,
    settings: Settings,
) -> list[ChunkCandidate]:
    paragraphs = _paragraphs(page.text)
    if not paragraphs:
        return []

    chunks: list[ChunkCandidate] = []
    group: list[tuple[int, int, str]] = []
    word_count = 0

    def flush() -> None:
        if not group:
            return
        text = " ".join(part[2] for part in group).strip()
        if not text:
            return
        is_ocr = page.source == "ocr"
        chunks.append(
            ChunkCandidate(
                page=page.page_number,
                line_start=group[0][0],
                line_end=group[-1][1],
                text=text,
                ocr_confidence=page.confidence if is_ocr else None,
                # An OCR chunk with a real box gets the finer bbox anchor;
                # without one it must not claim better precision than it has.
                anchor_quality="bbox" if (is_ocr and page.bbox is not None) else anchor_quality,
                fidelity_tier=fidelity_tier,
                bbox=page.bbox.as_tuple() if (is_ocr and page.bbox is not None) else None,
            )
        )

    for paragraph in paragraphs:
        paragraph_words = len(paragraph[2].split())
        if group and word_count + paragraph_words > settings.chunk_max_words:
            flush()
            # Carry the tail of the closed group forward so consecutive
            # chunks overlap, preserving local context across the boundary.
            overlap: list[tuple[int, int, str]] = []
            overlap_words = 0
            for part in reversed(group):
                part_words = len(part[2].split())
                if overlap_words + part_words > settings.chunk_overlap_words:
                    break
                overlap.insert(0, part)
                overlap_words += part_words
            group = overlap
            word_count = overlap_words
        group.append(paragraph)
        word_count += paragraph_words

    flush()
    return chunks


def chunk_document(
    parsed: ParsedDocument,
    settings: Settings,
    anchor_quality: AnchorQuality = "paragraph",
) -> list[ChunkCandidate]:
    candidates: list[ChunkCandidate] = []
    for page in parsed.pages:
        candidates.extend(_chunk_page(page, parsed.fidelity_tier, anchor_quality, settings))
        if len(candidates) >= settings.max_chunks_per_document:
            break
    return candidates[: settings.max_chunks_per_document]
