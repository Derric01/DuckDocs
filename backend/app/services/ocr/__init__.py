"""Pluggable OCR engines (docs/22_OCR_PIPELINE.md)."""

from app.services.ocr.base import BoundingBox, OcrEngine, OcrLine, OcrResult, aggregate_confidence
from app.services.ocr.paddle import PaddleOcrEngine
from app.services.ocr.rapid import RapidOcrEngine
from app.services.ocr.registry import build_engine, reset_engine_cache
from app.services.ocr.tesseract import TesseractOcrEngine

__all__ = [
    "BoundingBox",
    "OcrEngine",
    "OcrLine",
    "OcrResult",
    "PaddleOcrEngine",
    "RapidOcrEngine",
    "TesseractOcrEngine",
    "aggregate_confidence",
    "build_engine",
    "reset_engine_cache",
]
