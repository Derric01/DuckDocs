"""Engine selection.

`DUCKDOCS_OCR_ENGINE` picks the backend:
  auto (default) -- RapidOCR, then Tesseract
  rapidocr       -- RapidOCR only (PP-OCR models via ONNX, weights bundled)
  paddleocr      -- PaddleOCR only (upstream runtime; downloads weights)
  tesseract      -- Tesseract only

"auto" tries engines in order and falls back rather than failing ingestion.
Silently producing no text would violate the honest-failure rule, so the
engine that actually ran is recorded on every chunk it produces.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.ocr.base import OcrEngine
from app.services.ocr.paddle import PaddleOcrEngine
from app.services.ocr.rapid import RapidOcrEngine
from app.services.ocr.tesseract import TesseractOcrEngine


class NullOcrEngine:
    """Used when no engine can load. Recognizes nothing, but reports it."""

    name = "unavailable"

    def available(self) -> bool:
        return False

    def recognize(self, image: object, languages: str) -> object:
        from app.services.ocr.base import OcrResult

        return OcrResult("", None, self.name)

    def recognize_batch(self, images: list[object], languages: str) -> list[object]:
        from app.services.ocr.base import OcrResult

        return [OcrResult("", None, self.name) for _ in images]


_cache: dict[str, OcrEngine] = {}


def build_engine(settings: Settings) -> OcrEngine:
    """Return the engine for the configured preference, memoized per choice.

    Engines hold loaded models, so they are cached rather than rebuilt for
    every document.
    """
    preference = (settings.ocr_engine or "auto").strip().lower()
    cache_key = f"{preference}:{settings.ocr_languages}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    engine = _select(preference, settings)
    _cache[cache_key] = engine
    return engine


def _select(preference: str, settings: Settings) -> OcrEngine:
    if preference == "tesseract":
        tesseract = TesseractOcrEngine()
        return tesseract if tesseract.available() else NullOcrEngine()  # type: ignore[return-value]

    if preference == "paddleocr":
        paddle = PaddleOcrEngine(settings.ocr_languages, model_dir=settings.ocr_model_dir)
        return paddle if paddle.available() else NullOcrEngine()  # type: ignore[return-value]

    if preference == "rapidocr":
        rapid = RapidOcrEngine(settings.ocr_languages)
        return rapid if rapid.available() else NullOcrEngine()  # type: ignore[return-value]

    # auto: RapidOCR first (bundled weights, no download), then Tesseract.
    rapid = RapidOcrEngine(settings.ocr_languages)
    if rapid.available():
        return rapid
    tesseract = TesseractOcrEngine()
    if tesseract.available():
        return tesseract
    return NullOcrEngine()  # type: ignore[return-value]


def reset_engine_cache() -> None:
    """Test hook -- engines memoize loaded models across calls."""
    _cache.clear()
