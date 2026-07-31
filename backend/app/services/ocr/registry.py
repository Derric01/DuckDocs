"""Engine selection.

`DUCKDOCS_OCR_ENGINE` picks the backend:
  auto (default) -- PaddleOCR when it can load, otherwise Tesseract
  paddleocr      -- PaddleOCR only
  tesseract      -- Tesseract only

"auto" exists because PaddleOCR needs a one-time weights download. On a
machine that has never had network access those weights are absent, and
silently producing no text would violate the honest-failure rule -- falling
back to an engine whose data ships with the OS keeps ingestion working and
records which engine actually ran.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.ocr.base import OcrEngine
from app.services.ocr.paddle import PaddleOcrEngine
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

    paddle = PaddleOcrEngine(settings.ocr_languages, model_dir=settings.ocr_model_dir)
    if preference == "paddleocr":
        return paddle if paddle.available() else NullOcrEngine()  # type: ignore[return-value]

    # auto
    if paddle.available():
        return paddle
    tesseract = TesseractOcrEngine()
    if tesseract.available():
        return tesseract
    return NullOcrEngine()  # type: ignore[return-value]


def reset_engine_cache() -> None:
    """Test hook -- engines memoize loaded models across calls."""
    _cache.clear()
