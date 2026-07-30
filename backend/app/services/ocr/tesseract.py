"""Tesseract engine (offline fallback).

Kept as the fallback because its language data ships with the OS package and
needs no download, so recognition still works on a machine that has never
had network access -- the situation PaddleOCR's first run cannot cover.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.ocr.base import BoundingBox, OcrLine, OcrResult, aggregate_confidence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

try:
    from PIL import ImageOps
except ImportError:  # pragma: no cover
    ImageOps = None  # type: ignore[assignment]


def preprocess(image: Image.Image) -> Image.Image:
    """Grayscale + contrast stretch.

    Full deskew/denoise/binarize (docs/22 §5) needs an image-processing
    dependency beyond Pillow; these two steps are free and measurably help
    Tesseract on ordinary scans.
    """
    if ImageOps is None:  # pragma: no cover
        return image
    return ImageOps.autocontrast(ImageOps.grayscale(image))


class TesseractOcrEngine:
    name = "tesseract"

    def available(self) -> bool:
        if pytesseract is None:
            return False
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            return False
        return True

    def recognize(self, image: Image.Image, languages: str) -> OcrResult:
        if pytesseract is None:  # pragma: no cover
            return OcrResult("", None, self.name)
        prepared = preprocess(image)
        try:
            data: dict[str, Any] = pytesseract.image_to_data(
                prepared, lang=languages, output_type=pytesseract.Output.DICT
            )
        except Exception:
            return OcrResult("", None, self.name)
        return self._parse(data, prepared.width, prepared.height)

    def recognize_batch(self, images: list[Image.Image], languages: str) -> list[OcrResult]:
        # Tesseract has no batch API; pages are recognized sequentially.
        return [self.recognize(image, languages) for image in images]

    def _parse(self, data: dict[str, Any], width: int, height: int) -> OcrResult:
        texts = data.get("text", [])
        confs = data.get("conf", [])
        line_keys = list(
            zip(
                data.get("block_num", []),
                data.get("par_num", []),
                data.get("line_num", []),
                strict=False,
            )
        )

        grouped: dict[tuple[int, int, int], dict[str, Any]] = {}
        order: list[tuple[int, int, int]] = []
        all_confidences: list[float] = []

        for index, raw_text in enumerate(texts):
            word = str(raw_text).strip()
            if not word:
                continue
            confidence: float | None = None
            if index < len(confs):
                try:
                    value = float(confs[index])
                    if value >= 0:
                        confidence = value / 100.0
                        all_confidences.append(confidence)
                except (TypeError, ValueError):
                    confidence = None

            key = line_keys[index] if index < len(line_keys) else (0, 0, 0)
            bucket = grouped.get(key)
            if bucket is None:
                bucket = {"words": [], "confidences": [], "left": [], "top": [], "right": [], "bottom": []}
                grouped[key] = bucket
                order.append(key)
            bucket["words"].append(word)
            if confidence is not None:
                bucket["confidences"].append(confidence)
            try:
                left = float(data["left"][index])
                top = float(data["top"][index])
                bucket["left"].append(left)
                bucket["top"].append(top)
                bucket["right"].append(left + float(data["width"][index]))
                bucket["bottom"].append(top + float(data["height"][index]))
            except (KeyError, IndexError, TypeError, ValueError):
                pass

        lines: list[OcrLine] = []
        for key in order:
            bucket = grouped[key]
            bbox: BoundingBox | None = None
            if bucket["left"] and width > 0 and height > 0:
                left = min(bucket["left"]) / width
                top = min(bucket["top"]) / height
                right = max(bucket["right"]) / width
                bottom = max(bucket["bottom"]) / height
                if right > left and bottom > top:
                    bbox = BoundingBox(
                        round(max(0.0, left), 5),
                        round(max(0.0, top), 5),
                        round(min(1.0, right) - max(0.0, left), 5),
                        round(min(1.0, bottom) - max(0.0, top), 5),
                    )
            lines.append(
                OcrLine(
                    text=" ".join(bucket["words"]),
                    confidence=aggregate_confidence(bucket["confidences"]),
                    bbox=bbox,
                )
            )

        return OcrResult(
            text="\n".join(line.text for line in lines),
            confidence=aggregate_confidence(all_confidences),
            engine=self.name,
            lines=lines,
        )
