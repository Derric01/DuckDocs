"""PaddleOCR engine (default).

PaddleOCR runs entirely on the local machine: weights are fetched once on
first use and cached under the model directory, after which recognition is
offline with no API key, no per-page quota, and no request to any provider.
It is the default engine because, relative to Tesseract, it recognizes
low-quality scans and non-Latin scripts substantially better and returns
per-line quadrilaterals, which give citations real bounding-box anchors
(OCR-G01) instead of line-number approximations.

The adapter is deliberately tolerant: if the package is missing or the
weights have never been downloaded, `available()` returns False and the
registry falls back to Tesseract rather than failing ingestion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.ocr.base import BoundingBox, OcrLine, OcrResult, aggregate_confidence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

# PaddleOCR language codes differ from Tesseract's ISO-639-3 triples.
_LANGUAGE_ALIASES = {
    "eng": "en", "en": "en",
    "chi_sim": "ch", "chi_tra": "chinese_cht", "ch": "ch", "zh": "ch",
    "fra": "fr", "fr": "fr",
    "deu": "german", "de": "german",
    "spa": "es", "es": "es",
    "por": "pt", "pt": "pt",
    "rus": "ru", "ru": "ru",
    "jpn": "japan", "ja": "japan",
    "kor": "korean", "ko": "korean",
    "ara": "ar", "ar": "ar",
    "hin": "hi", "hi": "hi",
    "ita": "it", "it": "it",
}


def normalize_language(languages: str) -> str:
    """Map the configured language to a PaddleOCR code.

    DUCKDOCS_OCR_LANGUAGES may carry several Tesseract-style codes
    ("eng+chi_sim"); PaddleOCR takes exactly one, so the first is used.
    """
    first = languages.split("+")[0].strip().lower()
    return _LANGUAGE_ALIASES.get(first, first or "en")


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
    left, right = min(xs) / width, max(xs) / width
    top, bottom = min(ys) / height, max(ys) / height
    left, right = max(0.0, left), min(1.0, right)
    top, bottom = max(0.0, top), min(1.0, bottom)
    if right <= left or bottom <= top:
        return None
    return BoundingBox(round(left, 5), round(top, 5), round(right - left, 5), round(bottom - top, 5))


class PaddleOcrEngine:
    """Adapter over paddleocr.PaddleOCR. The model is loaded lazily and once."""

    name = "paddleocr"

    def __init__(self, languages: str = "eng", *, model_dir: str | None = None) -> None:
        self._language = normalize_language(languages)
        self._model_dir = model_dir
        self._reader: Any | None = None
        self._load_failed = False

    def _reader_for(self, languages: str) -> Any | None:
        language = normalize_language(languages)
        if self._reader is not None and language == self._language:
            return self._reader
        if self._load_failed and language == self._language:
            return None
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            self._load_failed = True
            return None
        try:
            kwargs: dict[str, Any] = {
                "lang": language,
                # Orientation/unwarping submodels add two more downloads and
                # meaningful CPU cost; the ingestion pipeline already renders
                # PDF pages upright, so they stay off by default.
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
            }
            if self._model_dir:
                kwargs["paddlex_config"] = self._model_dir
            self._reader = PaddleOCR(**kwargs)
            self._language = language
            self._load_failed = False
        except Exception:
            # Missing weights with no network, unsupported language pack, or a
            # paddle/paddlex version mismatch all land here. Ingestion must
            # degrade to the fallback engine, never crash.
            self._reader = None
            self._load_failed = True
        return self._reader

    def available(self) -> bool:
        return self._reader_for(self._language) is not None

    def recognize(self, image: Image.Image, languages: str) -> OcrResult:
        results = self.recognize_batch([image], languages)
        return results[0] if results else OcrResult("", None, self.name)

    def recognize_batch(self, images: list[Image.Image], languages: str) -> list[OcrResult]:
        if not images:
            return []
        reader = self._reader_for(languages)
        if reader is None:
            return [OcrResult("", None, self.name) for _ in images]

        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy ships with paddle
            return [OcrResult("", None, self.name) for _ in images]

        frames = [np.array(image.convert("RGB")) for image in images]
        try:
            # PaddleOCR batches a list of arrays in a single predict call.
            raw_results = reader.predict(frames)
        except Exception:
            return [OcrResult("", None, self.name) for _ in images]

        parsed: list[OcrResult] = []
        for index, image in enumerate(images):
            raw = raw_results[index] if index < len(raw_results) else None
            parsed.append(self._parse(raw, image.width, image.height))
        return parsed

    def _parse(self, raw: Any, width: int, height: int) -> OcrResult:
        if raw is None:
            return OcrResult("", None, self.name)
        # PaddleOCR 3.x returns a dict-like result object per image.
        try:
            texts = list(raw["rec_texts"])
            scores = list(raw["rec_scores"])
        except (KeyError, TypeError, IndexError):
            return OcrResult("", None, self.name)
        try:
            polys = list(raw["rec_polys"])
        except (KeyError, TypeError, IndexError):
            polys = []

        lines: list[OcrLine] = []
        confidences: list[float] = []
        for position, text in enumerate(texts):
            stripped = str(text).strip()
            if not stripped:
                continue
            confidence: float | None = None
            if position < len(scores):
                try:
                    confidence = max(0.0, min(1.0, float(scores[position])))
                    confidences.append(confidence)
                except (TypeError, ValueError):
                    confidence = None
            bbox = _quad_to_bbox(polys[position], width, height) if position < len(polys) else None
            lines.append(OcrLine(text=stripped, confidence=confidence, bbox=bbox))

        return OcrResult(
            text="\n".join(line.text for line in lines),
            confidence=aggregate_confidence(confidences),
            engine=self.name,
            lines=lines,
        )
