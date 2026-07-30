"""Document parsing and OCR (docs/21_FILE_PROCESSING.md, docs/22_OCR_PIPELINE.md).

Every supported upload format normalizes into a `ParsedDocument`: an ordered
list of pages, each carrying its own text, provenance (native text layer vs.
OCR), and — when OCR was used — a confidence score. This is the seam the
chunker (`app/services/chunking.py`) builds evidence anchors from.

OCR runs fully locally through a pluggable engine (`app/services/ocr`,
PaddleOCR by default) with no page cap and no per-document quota: every page
of a scanned PDF is recognized, not just a sampled prefix. Scanned pages are
recognized in batches so a long document amortizes model overhead instead of
paying it per page. Confidence and bounding boxes are always captured and
never silently discarded (RULE-10) — low-confidence OCR is labeled, not
hidden.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from xml.etree import ElementTree

from app.core.config import Settings
from app.domain.models import FidelityTier
from app.services.ocr import BoundingBox, OcrEngine, build_engine

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - exercised only if dependency missing
    fitz = None

try:
    from PIL import Image, ImageSequence
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

try:
    from pptx import Presentation
except ImportError:  # pragma: no cover
    Presentation = None  # type: ignore[assignment]

PageSource = Literal["native", "ocr"]
ProgressCallback = Callable[[int, int], None]

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

CODE_EXTENSIONS = {
    "ts", "tsx", "js", "jsx", "py", "java", "c", "cpp", "cc", "h", "hpp",
    "cs", "go", "rs", "sql", "css", "sh", "rb", "php", "kt", "swift",
}
STRUCTURED_TEXT_EXTENSIONS = {"json", "xml", "yaml", "yml"}
PLAIN_TEXT_EXTENSIONS = {"txt", "md"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp"}

SUPPORTED_EXTENSIONS = (
    {"pdf", "docx", "csv", "html", "htm", "xlsx", "pptx"}
    | CODE_EXTENSIONS
    | STRUCTURED_TEXT_EXTENSIONS
    | PLAIN_TEXT_EXTENSIONS
    | IMAGE_EXTENSIONS
)


@dataclass(slots=True)
class ParsedPage:
    page_number: int
    text: str
    source: PageSource
    confidence: float | None = None
    bbox: BoundingBox | None = None
    engine: str | None = None


@dataclass(slots=True)
class ParsedDocument:
    pages: list[ParsedPage]
    fidelity_tier: FidelityTier
    page_count: int
    ocr_engine: str | None = None


def parse_upload(
    payload: bytes,
    suffix: str,
    settings: Settings,
    on_page: ProgressCallback | None = None,
) -> ParsedDocument | None:
    """Dispatch to the parser for `suffix`. Returns None for unrecognized types.

    `on_page(current, total)` is invoked as pages are recognized for formats
    that can take a while (PDF OCR fallback, multi-frame images) so callers
    can report incremental progress; other formats parse fast enough that
    it isn't needed and the callback is simply never called.
    """
    if suffix == "pdf":
        return parse_pdf(payload, settings, on_page)
    if suffix == "docx":
        return parse_docx(payload)
    if suffix == "xlsx":
        return parse_xlsx(payload)
    if suffix == "pptx":
        return parse_pptx(payload)
    if suffix in IMAGE_EXTENSIONS:
        return parse_image(payload, settings, on_page)
    if suffix == "csv":
        return parse_csv(payload)
    if suffix in {"html", "htm"}:
        return parse_html(payload)
    if suffix in CODE_EXTENSIONS | STRUCTURED_TEXT_EXTENSIONS | PLAIN_TEXT_EXTENSIONS:
        return parse_plain_text(payload)
    return None


def _has_min_alnum(text: str, minimum: int = 20) -> bool:
    return len(re.findall(r"[A-Za-z0-9]", text)) >= minimum


def _decode(payload: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def parse_plain_text(payload: bytes) -> ParsedDocument | None:
    decoded = _decode(payload)
    if decoded is None:
        return None
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", decoded)[:400_000]
    if not _has_min_alnum(cleaned):
        return None
    return ParsedDocument(pages=[ParsedPage(1, cleaned, "native")], fidelity_tier="full_layout", page_count=1)


def parse_csv(payload: bytes) -> ParsedDocument | None:
    decoded = _decode(payload)
    if decoded is None:
        return None
    try:
        rows = list(csv.reader(io.StringIO(decoded)))
    except csv.Error:
        return None
    lines = [" | ".join(cell.strip() for cell in row if cell.strip()) for row in rows]
    text = "\n".join(line for line in lines if line).strip()
    if not _has_min_alnum(text):
        return None
    return ParsedDocument(pages=[ParsedPage(1, text, "native")], fidelity_tier="structural", page_count=1)


class _TextOnlyHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.chunks.append(data.strip())


def parse_html(payload: bytes) -> ParsedDocument | None:
    decoded = _decode(payload)
    if decoded is None:
        return None
    parser = _TextOnlyHTMLParser()
    try:
        parser.feed(decoded)
    except Exception:
        return None
    text = re.sub(r"\n{3,}", "\n\n", " ".join(parser.chunks).replace(" \n ", "\n")).strip()
    if not _has_min_alnum(text):
        return None
    return ParsedDocument(pages=[ParsedPage(1, text, "native")], fidelity_tier="structural", page_count=1)


def parse_docx(payload: bytes) -> ParsedDocument | None:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            part_names = sorted(
                name
                for name in archive.namelist()
                if name == "word/document.xml" or name.startswith("word/header") or name.startswith("word/footer")
            )
            pages_parts: list[list[str]] = [[]]
            for part_name in part_names:
                root = ElementTree.fromstring(archive.read(part_name))
                for node in root.iter():
                    if node.tag == f"{WORD_NS}br" and node.get(f"{WORD_NS}type") == "page":
                        pages_parts.append([])
                    elif node.tag.endswith("}t") and node.text:
                        pages_parts[-1].append(node.text)
                    elif node.tag.endswith("}tab"):
                        pages_parts[-1].append("\t")
                    elif node.tag.endswith("}br") or node.tag.endswith("}p"):
                        pages_parts[-1].append("\n")
    except (ElementTree.ParseError, KeyError, OSError, zipfile.BadZipFile):
        return None

    pages: list[ParsedPage] = []
    for index, parts in enumerate(pages_parts, start=1):
        text = re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()
        if text and _has_min_alnum(text):
            pages.append(ParsedPage(index, text, "native"))
    if not pages:
        return None
    return ParsedDocument(pages=pages, fidelity_tier="full_layout", page_count=len(pages))


def parse_xlsx(payload: bytes) -> ParsedDocument | None:
    if openpyxl is None:  # pragma: no cover
        return None
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    except Exception:
        return None
    pages: list[ParsedPage] = []
    for index, sheet in enumerate(workbook.worksheets, start=1):
        lines: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if cells:
                lines.append(" | ".join(cells))
        body = "\n".join(lines).strip()
        if body:
            pages.append(ParsedPage(index, f"Sheet: {sheet.title}\n{body}", "native"))
    workbook.close()
    if not pages:
        return None
    return ParsedDocument(pages=pages, fidelity_tier="structural", page_count=len(pages))


def parse_pptx(payload: bytes) -> ParsedDocument | None:
    if Presentation is None:  # pragma: no cover
        return None
    try:
        presentation = Presentation(io.BytesIO(payload))
    except Exception:
        return None
    pages: list[ParsedPage] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                line = "".join(run.text for run in paragraph.runs).strip()
                if line:
                    lines.append(line)
        body = "\n".join(lines).strip()
        if body:
            pages.append(ParsedPage(index, f"Slide {index}\n{body}", "native"))
    if not pages:
        return None
    return ParsedDocument(pages=pages, fidelity_tier="structural", page_count=len(pages))


def _ocr_pages(
    images: list[Image.Image],
    settings: Settings,
    engine: OcrEngine,
    start_index: int = 1,
    on_page: ProgressCallback | None = None,
    total_override: int | None = None,
) -> list[ParsedPage]:
    """Recognize images in batches, reporting progress as each batch lands.

    Batching matters for throughput: PaddleOCR amortizes model overhead across
    a batch, so a long scanned document is materially faster than one call per
    page. Batch size is bounded so peak memory stays predictable on a large
    document rather than scaling with page count.
    """
    pages: list[ParsedPage] = []
    total = total_override if total_override is not None else len(images)
    batch_size = max(1, settings.ocr_batch_size)

    for offset in range(0, len(images), batch_size):
        batch = images[offset : offset + batch_size]
        results = engine.recognize_batch(batch, settings.ocr_languages)
        for position, result in enumerate(results):
            page_number = start_index + offset + position
            pages.append(
                ParsedPage(
                    page_number=page_number,
                    text=result.text.strip(),
                    source="ocr",
                    confidence=result.confidence,
                    bbox=result.envelope,
                    engine=result.engine,
                )
            )
            if on_page:
                on_page(page_number, total)
    return pages


def parse_image(payload: bytes, settings: Settings, on_page: ProgressCallback | None = None) -> ParsedDocument | None:
    if Image is None:  # pragma: no cover
        return None
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception:
        return None

    frame_count = int(getattr(image, "n_frames", 1) or 1)
    frames = (
        [frame.convert("RGB") for frame in ImageSequence.Iterator(image)]
        if frame_count > 1
        else [image.convert("RGB")]
    )

    engine = build_engine(settings)
    pages = _ocr_pages(frames, settings, engine, start_index=1, on_page=on_page)
    if not pages or not any(page.text for page in pages):
        return None
    return ParsedDocument(
        pages=pages,
        fidelity_tier="ocr_dependent",
        page_count=len(pages),
        ocr_engine=engine.name,
    )


def parse_pdf(payload: bytes, settings: Settings, on_page: ProgressCallback | None = None) -> ParsedDocument | None:
    if fitz is None:  # pragma: no cover
        return None
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return None

    native_pages: dict[int, ParsedPage] = {}
    scan_numbers: list[int] = []
    scan_images: list[Image.Image] = []
    native_fallback: dict[int, str] = {}
    total = document.page_count

    try:
        for index in range(total):
            page = document.load_page(index)
            page_number = index + 1
            native_text = page.get_text("text").strip()

            if len(native_text) >= settings.ocr_min_chars_per_page:
                native_pages[page_number] = ParsedPage(page_number, native_text, "native")
                if on_page:
                    on_page(page_number, total)
                continue

            # Text layer absent or sparse -- this page needs OCR. Every such
            # page is queued; there is no cap on how many scanned pages a
            # document may have (OCR-G02/OCR-AD-03).
            if Image is not None:
                pixmap = page.get_pixmap(dpi=settings.ocr_dpi)
                scan_images.append(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))
                scan_numbers.append(page_number)
                if native_text:
                    native_fallback[page_number] = native_text
            elif native_text:  # pragma: no cover
                native_pages[page_number] = ParsedPage(page_number, native_text, "native")
    finally:
        document.close()

    engine = build_engine(settings)
    ocr_pages: dict[int, ParsedPage] = {}
    if scan_images:
        # Progress is reported against the whole document so the job bar
        # reflects real position, not position within the scanned subset.
        recognized = _ocr_pages(
            scan_images,
            settings,
            engine,
            start_index=1,
            on_page=None,
            total_override=total,
        )
        for position, parsed in enumerate(recognized):
            page_number = scan_numbers[position]
            parsed.page_number = page_number
            if parsed.text:
                ocr_pages[page_number] = parsed
            elif page_number in native_fallback:
                ocr_pages[page_number] = ParsedPage(page_number, native_fallback[page_number], "native")
            if on_page:
                on_page(page_number, total)

    pages = [
        page
        for page in (native_pages.get(number) or ocr_pages.get(number) for number in range(1, total + 1))
        if page is not None
    ]
    if not pages:
        return None

    ocr_used = any(page.source == "ocr" for page in pages)
    return ParsedDocument(
        pages=pages,
        fidelity_tier="ocr_dependent" if ocr_used else "full_layout",
        page_count=len(pages),
        ocr_engine=engine.name if ocr_used else None,
    )
