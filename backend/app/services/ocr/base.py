"""OCR engine abstraction (docs/22_OCR_PIPELINE.md §10, OCR-AD-01).

Recognition sits behind a stable interface so the backend can be swapped --
PaddleOCR, Tesseract, or a future engine -- without the ingestion pipeline,
chunker, or evidence model changing. Every engine returns the same
`OcrResult`: text, an aggregated confidence, and per-line boxes in
normalized page coordinates (top-left origin, 0-1 range) so citation
anchors stay independent of the DPI a page was rasterized at (OCR-AD-07).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image


@dataclass(slots=True)
class BoundingBox:
    """Normalized page-relative box: top-left origin, x right, y down, 0-1."""

    x: float
    y: float
    width: float
    height: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)


@dataclass(slots=True)
class OcrLine:
    text: str
    confidence: float | None = None
    bbox: BoundingBox | None = None


@dataclass(slots=True)
class OcrResult:
    text: str
    confidence: float | None
    engine: str
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def envelope(self) -> BoundingBox | None:
        """Smallest box containing every recognized line."""
        boxes = [line.bbox for line in self.lines if line.bbox is not None]
        if not boxes:
            return None
        left = min(box.x for box in boxes)
        top = min(box.y for box in boxes)
        right = max(box.x + box.width for box in boxes)
        bottom = max(box.y + box.height for box in boxes)
        return BoundingBox(left, top, right - left, bottom - top)


EMPTY_RESULT = OcrResult(text="", confidence=None, engine="none", lines=[])


@runtime_checkable
class OcrEngine(Protocol):
    """Recognition backend. Implementations must not perform network calls at
    recognition time -- any model download happens once at load time."""

    name: str

    def available(self) -> bool:
        """True when the engine can actually recognize right now (imports
        resolved and weights present). Never raises."""
        ...

    def recognize(self, image: Image.Image, languages: str) -> OcrResult: ...

    def recognize_batch(self, images: list[Image.Image], languages: str) -> list[OcrResult]:
        """Recognize several pages. Engines with real batching override this;
        the default keeps correctness for engines that only do one page."""
        ...


def aggregate_confidence(values: list[float]) -> float | None:
    """Mean confidence over recognized units.

    Low-confidence units are deliberately included rather than filtered:
    discarding them would inflate the score and hide uncertainty, which
    RULE-10 forbids.
    """
    if not values:
        return None
    return max(0.0, min(1.0, sum(values) / len(values)))
