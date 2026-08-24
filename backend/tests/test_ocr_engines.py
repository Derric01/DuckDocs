"""OCR engine abstraction tests (docs/22_OCR_PIPELINE.md).

PaddleOCR's weights cannot be downloaded in every environment (offline CI,
restricted egress), so its adapter is tested against a stubbed reader. That
covers the part this repo actually owns -- result parsing, coordinate
normalization, language mapping, batching, and failure handling -- without
requiring the model to be present. The Tesseract engine is exercised for
real, since its language data ships with the OS package.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings
from app.services.ocr import RapidOcrEngine, TesseractOcrEngine, build_engine, reset_engine_cache
from app.services.ocr.base import BoundingBox, OcrLine, OcrResult, aggregate_confidence
from app.services.ocr.paddle import PaddleOcrEngine, _quad_to_bbox, normalize_language
from app.services.ocr.registry import NullOcrEngine


def _text_image(text: str, size: tuple[int, int] = (900, 220)) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 80), text, fill="black", font=font)
    return image


# --- base -----------------------------------------------------------------


def test_aggregate_confidence_includes_low_values() -> None:
    # Low scores must drag the mean down, not be filtered out (RULE-10).
    assert aggregate_confidence([1.0, 0.0]) == pytest.approx(0.5)
    assert aggregate_confidence([]) is None


def test_envelope_spans_every_line_box() -> None:
    result = OcrResult(
        text="a\nb",
        confidence=0.9,
        engine="stub",
        lines=[
            OcrLine("a", 0.9, BoundingBox(0.1, 0.1, 0.2, 0.1)),
            OcrLine("b", 0.9, BoundingBox(0.5, 0.4, 0.2, 0.2)),
        ],
    )
    envelope = result.envelope
    assert envelope is not None
    assert envelope.x == pytest.approx(0.1)
    assert envelope.y == pytest.approx(0.1)
    assert envelope.width == pytest.approx(0.6)
    assert envelope.height == pytest.approx(0.5)


def test_envelope_is_none_without_boxes() -> None:
    assert OcrResult("a", 0.5, "stub", [OcrLine("a")]).envelope is None


# --- paddle adapter -------------------------------------------------------


def test_language_aliases_map_to_paddle_codes() -> None:
    assert normalize_language("eng") == "en"
    assert normalize_language("chi_sim") == "ch"
    assert normalize_language("jpn") == "japan"
    # Multi-language config takes the first entry (PaddleOCR accepts one).
    assert normalize_language("eng+chi_sim") == "en"
    # Unknown codes pass through rather than being silently rewritten.
    assert normalize_language("xyz") == "xyz"


def test_quad_to_bbox_normalizes_pixels() -> None:
    quad = [[100, 50], [300, 50], [300, 90], [100, 90]]
    bbox = _quad_to_bbox(quad, width=1000, height=200)
    assert bbox is not None
    assert bbox.x == pytest.approx(0.1)
    assert bbox.y == pytest.approx(0.25)
    assert bbox.width == pytest.approx(0.2)
    assert bbox.height == pytest.approx(0.2)


def test_quad_to_bbox_rejects_degenerate_input() -> None:
    assert _quad_to_bbox([[0, 0], [0, 0], [0, 0], [0, 0]], 100, 100) is None
    assert _quad_to_bbox("nonsense", 100, 100) is None
    assert _quad_to_bbox([[0, 0], [10, 10]], 0, 0) is None


class _StubReader:
    """Mimics paddleocr.PaddleOCR.predict for a batch of images."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[int] = []

    def predict(self, frames: list[Any]) -> list[dict[str, Any]]:
        self.calls.append(len(frames))
        return self.payloads[: len(frames)]


def _paddle_with_reader(reader: Any) -> PaddleOcrEngine:
    engine = PaddleOcrEngine("eng")
    engine._reader = reader
    engine._language = "en"
    return engine


def test_paddle_parses_texts_scores_and_boxes() -> None:
    reader = _StubReader(
        [
            {
                "rec_texts": ["Retention window", "eighteen months"],
                "rec_scores": [0.98, 0.90],
                "rec_polys": [
                    [[0, 0], [450, 0], [450, 40], [0, 40]],
                    [[0, 60], [300, 60], [300, 100], [0, 100]],
                ],
            }
        ]
    )
    engine = _paddle_with_reader(reader)
    result = engine.recognize(Image.new("RGB", (900, 200), "white"), "eng")

    assert result.engine == "paddleocr"
    assert result.text == "Retention window\neighteen months"
    assert result.confidence == pytest.approx(0.94)
    assert len(result.lines) == 2
    assert result.lines[0].bbox is not None
    assert result.lines[0].bbox.x == pytest.approx(0.0)
    assert result.lines[0].bbox.width == pytest.approx(0.5)
    assert result.envelope is not None


def test_paddle_skips_blank_text_entries() -> None:
    reader = _StubReader([{"rec_texts": ["real", "   ", ""], "rec_scores": [0.9, 0.1, 0.1], "rec_polys": []}])
    result = _paddle_with_reader(reader).recognize(Image.new("RGB", (100, 100)), "eng")
    assert result.text == "real"
    assert len(result.lines) == 1


def test_paddle_batches_in_a_single_predict_call() -> None:
    payloads = [
        {"rec_texts": [f"page {index}"], "rec_scores": [0.9], "rec_polys": []} for index in range(3)
    ]
    reader = _StubReader(payloads)
    engine = _paddle_with_reader(reader)
    images = [Image.new("RGB", (80, 40)) for _ in range(3)]

    results = engine.recognize_batch(images, "eng")

    assert [result.text for result in results] == ["page 0", "page 1", "page 2"]
    assert reader.calls == [3], "all three pages should go through one predict call"


def test_paddle_returns_empty_results_when_predict_raises() -> None:
    class _Exploding:
        def predict(self, frames: list[Any]) -> list[Any]:
            raise RuntimeError("inference failed")

    engine = _paddle_with_reader(_Exploding())
    results = engine.recognize_batch([Image.new("RGB", (10, 10))], "eng")
    assert len(results) == 1
    assert results[0].text == ""
    assert results[0].confidence is None


def test_paddle_handles_malformed_result_payload() -> None:
    engine = _paddle_with_reader(_StubReader([{"unexpected": True}]))
    result = engine.recognize(Image.new("RGB", (10, 10)), "eng")
    assert result.text == ""


def test_paddle_unavailable_when_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "paddleocr":
            raise ImportError("paddleocr not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert PaddleOcrEngine("eng").available() is False


# --- tesseract engine (real) ---------------------------------------------


def test_tesseract_recognizes_text_with_confidence_and_boxes() -> None:
    engine = TesseractOcrEngine()
    if not engine.available():  # pragma: no cover - depends on host packages
        pytest.skip("tesseract binary not installed")

    result = engine.recognize(_text_image("Northwind lease renewal"), "eng")
    assert result.engine == "tesseract"
    assert "Northwind" in result.text or "lease" in result.text.lower()
    assert result.confidence is not None and 0.0 <= result.confidence <= 1.0
    assert result.lines
    assert result.envelope is not None


def test_tesseract_batch_matches_input_length() -> None:
    engine = TesseractOcrEngine()
    if not engine.available():  # pragma: no cover
        pytest.skip("tesseract binary not installed")
    results = engine.recognize_batch([_text_image("Alpha"), _text_image("Beta")], "eng")
    assert len(results) == 2


def test_tesseract_returns_empty_on_unusable_image() -> None:
    engine = TesseractOcrEngine()
    if not engine.available():  # pragma: no cover
        pytest.skip("tesseract binary not installed")
    blank = Image.open(io.BytesIO(_blank_png()))
    result = engine.recognize(blank, "eng")
    assert result.text.strip() == ""


def _blank_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (60, 60), "white").save(buffer, format="PNG")
    return buffer.getvalue()


# --- registry -------------------------------------------------------------


def test_explicit_tesseract_preference_selects_tesseract() -> None:
    reset_engine_cache()
    engine = build_engine(Settings(ocr_engine="tesseract"))
    assert engine.name in {"tesseract", "unavailable"}


def test_auto_falls_back_when_rapidocr_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_engine_cache()
    monkeypatch.setattr(RapidOcrEngine, "available", lambda self: False)
    engine = build_engine(Settings(ocr_engine="auto"))
    assert engine.name in {"tesseract", "unavailable"}
    reset_engine_cache()


def test_auto_prefers_rapidocr_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_engine_cache()
    monkeypatch.setattr(RapidOcrEngine, "available", lambda self: True)
    engine = build_engine(Settings(ocr_engine="auto"))
    assert engine.name == "rapidocr"
    reset_engine_cache()


def test_explicit_paddle_preference_is_still_selectable(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_engine_cache()
    monkeypatch.setattr(PaddleOcrEngine, "available", lambda self: True)
    assert build_engine(Settings(ocr_engine="paddleocr")).name == "paddleocr"
    reset_engine_cache()


def test_engine_is_cached_per_preference(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_engine_cache()
    monkeypatch.setattr(RapidOcrEngine, "available", lambda self: True)
    settings = Settings(ocr_engine="auto")
    assert build_engine(settings) is build_engine(settings), "loaded models must not be rebuilt per document"
    reset_engine_cache()


def test_null_engine_reports_unavailable() -> None:
    null = NullOcrEngine()
    assert null.available() is False
    assert null.recognize_batch([object(), object()], "eng") != []
