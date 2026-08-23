"""RapidOCR engine (default).

Runs the same PP-OCR detection/recognition models as PaddleOCR, but through
ONNX Runtime and with the weights shipped inside the wheel. That removes the
two things that made PaddleOCR awkward here:

  * no first-run download, so recognition works on a machine that has never
    had network access — the case Tesseract previously had to cover alone;
  * none of the `paddlex` dependency tree (langchain, openai, pandas,
    scikit-learn), which a local-first product should not be shipping at all.

Accuracy is equivalent because the models are the same. PaddleOCR remains
selectable for anyone who wants the upstream runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.ocr.base import BoundingBox, OcrLine, OcrResult, aggregate_confidence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image


def _quad_to_bbox(quad: Any, width: int, height: int) -> BoundingBox | None:
    """Convert a 4-point polygon in pixels to a normalized axis-aligned box."""
    try:
        points = [(float(point[0]), float(point[1])) for point in quad]
    except (TypeError, ValueError, IndexError):
        return None
    if not points or width <= 0 or height <= 0:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left, right = max(0.0, min(xs) / width), min(1.0, max(xs) / width)
    top, bottom = max(0.0, min(ys) / height), min(1.0, max(ys) / height)
    if right <= left or bottom <= top:
        return None
    return BoundingBox(round(left, 5), round(top, 5), round(right - left, 5), round(bottom - top, 5))


class RapidOcrEngine:
    """Adapter over rapidocr_onnxruntime.RapidOCR. Model loads lazily, once."""

    name = "rapidocr"

    def __init__(self, languages: str = "eng") -> None:
        # RapidOCR's bundled models cover Latin scripts plus Chinese in one
        # set, so unlike PaddleOCR there is no per-language model to select.
        self._languages = languages
        self._reader: Any | None = None
        self._load_failed = False

    def _get_reader(self) -> Any | None:
        if self._reader is not None:
            return self._reader
        if self._load_failed:
            return None
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            self._load_failed = True
            return None
        try:
            self._reader = RapidOCR()
        except Exception:
            self._reader = None
            self._load_failed = True
        return self._reader

    def available(self) -> bool:
        return self._get_reader() is not None

    def recognize(self, image: Image.Image, languages: str) -> OcrResult:
        reader = self._get_reader()
        if reader is None:
            return OcrResult("", None, self.name)

        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy ships with onnxruntime
            return OcrResult("", None, self.name)

        rgb = image.convert("RGB")
        try:
            raw, _elapse = reader(np.array(rgb))
        except Exception:
            return OcrResult("", None, self.name)

        return self._parse(raw, rgb.width, rgb.height)

    def recognize_batch(self, images: list[Image.Image], languages: str) -> list[OcrResult]:
        # RapidOCR's ONNX session takes one image per call; the loop keeps the
        # engine contract while the session itself is reused across pages,
        # which is where most of the per-page cost would otherwise go.
        return [self.recognize(image, languages) for image in images]

    def _parse(self, raw: Any, width: int, height: int) -> OcrResult:
        # RapidOCR returns [[quad, text, score], ...], or None for a blank page.
        if not raw:
            return OcrResult("", None, self.name)

        lines: list[OcrLine] = []
        confidences: list[float] = []
        for entry in raw:
            try:
                quad, text, score = entry[0], entry[1], entry[2]
            except (TypeError, IndexError):
                continue
            stripped = str(text).strip()
            if not stripped:
                continue
            confidence: float | None = None
            try:
                confidence = max(0.0, min(1.0, float(score)))
                confidences.append(confidence)
            except (TypeError, ValueError):
                confidence = None
            lines.append(
                OcrLine(text=stripped, confidence=confidence, bbox=_quad_to_bbox(quad, width, height))
            )

        return OcrResult(
            text="\n".join(line.text for line in lines),
            confidence=aggregate_confidence(confidences),
            engine=self.name,
            lines=lines,
        )
