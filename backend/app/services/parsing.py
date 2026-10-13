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
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from html.parser import HTMLParser
from typing import Literal
from xml.etree import ElementTree
import yaml

from app.core.config import Settings
from app.domain.models import FidelityTier, TableRow, KeyValue
from app.services.ocr import BoundingBox, OcrEngine, build_engine
from app.services.docx_pages import DocxBlock, read_docx

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
    table_rows: list[TableRow] = field(default_factory=list)
    key_values: list[KeyValue] = field(default_factory=list)
    docx_blocks: list[DocxBlock] = field(default_factory=list)


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
    try:
        suffix = detect_file_type(payload, suffix)
    except FileDetectionError:
        return None
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
    if suffix in STRUCTURED_TEXT_EXTENSIONS:
        return parse_key_values(payload, suffix)
    if suffix in CODE_EXTENSIONS | STRUCTURED_TEXT_EXTENSIONS | PLAIN_TEXT_EXTENSIONS:
        return parse_plain_text(payload)
    return None


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    pairs = loader.construct_pairs(node, deep=deep)
    return _unique_pairs(pairs)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if not isinstance(key, (str, int, float, bool)) or key in result:
            raise ValueError("Structured keys must be unique scalar values.")
        result[key] = value
    return result


_UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def parse_key_values(payload: bytes, suffix: str) -> ParsedDocument | None:
    decoded = _decode(payload)
    if decoded is None:
        return None
    values: list[KeyValue] = []
    active: set[int] = set()
    visits = 0

    def add(path, keys, value, kind):
        values.append(KeyValue(path=path, keys=keys, value=value, value_type=kind))

    def check(depth):
        nonlocal visits
        visits += 1
        if depth > 64 or visits > 20_000:
            raise ValueError("Structured document exceeds safe nesting or node limits.")

    def walk(value, path, keys, depth=0):
        check(depth)
        if isinstance(value, (dict, list)) and value:
            if id(value) in active:
                raise ValueError("Cyclic YAML aliases are not supported.")
            active.add(id(value))
            try:
                if isinstance(value, dict):
                    for key, child in value.items():
                        key = str(key)
                        component = f".{key}" if re.fullmatch(r"[A-Za-z_][\w-]*", key) else f"[{json.dumps(key, ensure_ascii=False)}]"
                        walk(child, path + component, keys + [key], depth + 1)
                else:
                    for index, child in enumerate(value):
                        walk(child, f"{path}[{index}]", keys + [str(index)], depth + 1)
            finally:
                active.remove(id(value))
        else:
            text = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)
            add(path, keys, text, type(value).__name__)

    def xml_walk(node, path, keys, depth=0):
        check(depth)
        for attribute, text in node.attrib.items():
            add(f"{path}/@{attribute}", keys + [f"@{attribute}"], text, "attribute")
        text = (node.text or "").strip()
        if text:
            add(path, keys, text, "text")
        siblings = {}
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
        for child in node:
            siblings[child.tag] = siblings.get(child.tag, 0) + 1
            name = child.tag
            component = f"{name}[{siblings[name]}]" if counts[name] > 1 else name
            xml_walk(child, f"{path}/{component}", keys + [name], depth + 1)
            if (child.tail or "").strip():
                add(f"{path}/text()[{len(values)}]", keys, child.tail.strip(), "text")

    try:
        if suffix == "json":
            value = json.loads(decoded, object_pairs_hook=_unique_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))
            walk(value, "$", [])
        elif suffix in {"yaml", "yml"}:
            walk(yaml.load(decoded, Loader=_UniqueSafeLoader), "$", [])
        else:
            if re.search(r"<!DOCTYPE|<!ENTITY", decoded, re.I):
                return None
            root = ElementTree.fromstring(decoded)
            xml_walk(root, f"/{root.tag}", [root.tag])
    except (ValueError, TypeError, RecursionError, yaml.YAMLError, ElementTree.ParseError):
        return None
    if not values:
        return None
    for value in values:
        value.unit_count = len(values)
    return ParsedDocument([ParsedPage(1, "\n".join(v.quote() for v in values), "native", key_values=values)],
                          "structural", 1)


def probe_page_count(payload: bytes, suffix: str) -> int:
    """How many pages the file structurally has, regardless of extraction.

    Page count is a property of the file, not of whether text extraction
    succeeded. Deriving it from parse output means a scanned document whose
    OCR returned nothing reports one page and cannot be paged through in the
    preview -- exactly when a user most needs to look at the real page.
    """
    if suffix == "pdf" and fitz is not None:
        try:
            document = fitz.open(stream=payload, filetype="pdf")
        except Exception:
            return 1
        try:
            return max(1, int(document.page_count))
        finally:
            document.close()

    if suffix in IMAGE_EXTENSIONS and Image is not None:
        try:
            image = Image.open(io.BytesIO(payload))
            image.load()
            return max(1, int(getattr(image, "n_frames", 1) or 1))
        except Exception:
            return 1

    return 1


def _has_min_alnum(text: str, minimum: int = 20) -> bool:
    return len(re.findall(r"[A-Za-z0-9]", text)) >= minimum


def _decode(payload: bytes) -> str | None:
    # A text extension is not proof that the payload is text. In particular,
    # Latin-1 decodes every possible byte sequence, which used to turn binary
    # uploads into apparently successful (and unsearchable) documents.
    if not payload or b"\x00" in payload:
        return None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            decoded = payload.decode(encoding)
            if decoded:
                printable = sum(char.isprintable() or char in "\t\r\n" for char in decoded)
                if printable / len(decoded) < 0.95:
                    return None
            return decoded
        except UnicodeDecodeError:
            continue
    return None


class FileDetectionError(ValueError):
    """Human-readable content rejection, surfaced by upload and retry."""


def detected_mime(suffix: str) -> str:
    return {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
            "tiff": "image/tiff", "tif": "image/tiff", "bmp": "image/bmp", "csv": "text/csv",
            "json": "application/json", "xml": "application/xml", "yaml": "application/yaml",
            "yml": "application/yaml", "html": "text/html", "htm": "text/html"}.get(suffix, "text/plain")


def detect_file_type(payload: bytes, suffix: str) -> str:
    """Recognized binary signatures override names; ambiguous text uses its suffix."""
    suffix = suffix.lower().lstrip(".")
    if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                infos = archive.infolist()
                if sum(info.file_size for info in infos) > 100 * 1024 * 1024 or any(info.flag_bits & 1 for info in infos):
                    raise FileDetectionError("This Office archive is encrypted or expands beyond the 100 MB parsing limit.")
                names = set(archive.namelist())
                formats = [kind for kind, member in {"xlsx": "xl/workbook.xml", "docx": "word/document.xml",
                                                      "pptx": "ppt/presentation.xml"}.items() if member in names]
                if len(formats) != 1:
                    raise FileDetectionError("This ZIP file is not an unambiguous Excel, Word or PowerPoint document.")
                return formats[0]
        except (zipfile.BadZipFile, OSError) as exc:
            raise FileDetectionError("This file has a ZIP/Office signature but its archive is corrupt.") from exc
    signatures = [(b"%PDF-", "pdf"), (b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"),
                  (b"II*\x00", "tiff"), (b"MM\x00*", "tiff"), (b"BM", "bmp")]
    for magic, kind in signatures:
        if payload.startswith(magic):
            return suffix if (kind, suffix) in {("jpg", "jpeg"), ("tiff", "tif")} else kind
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "webp"
    if payload.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise FileDetectionError("Legacy binary Office files are unsupported. Export the file as XLSX, DOCX or PPTX.")
    if payload.startswith((b"GIF87a", b"GIF89a")):
        raise FileDetectionError("GIF files are unsupported. Convert the image to PNG or JPEG.")
    decoded = _decode(payload)
    if decoded is None:
        raise FileDetectionError("The file has unrecognized binary content; renaming its extension will not make it readable.")
    stripped = decoded.lstrip()
    if re.match(r"<!doctype\s+html\b|<html\b", stripped, re.I):
        return "html"
    if re.match(r"<\?xml\b|<[A-Za-z_][\w:.-]*(?:\s|>)", stripped) and suffix not in CODE_EXTENSIONS:
        return "html" if suffix in {"html", "htm"} else "xml"
    if stripped.startswith(("{", "[")) and suffix not in CODE_EXTENSIONS:
        try:
            json.loads(stripped)
            return suffix if suffix in {"yaml", "yml"} else "json"
        except ValueError:
            pass
    if suffix in {"pdf", "docx", "xlsx", "pptx"} | IMAGE_EXTENSIONS:
        raise FileDetectionError(f"The content is plain text, not a valid {suffix.upper()} file. Export it in the intended format.")
    if suffix not in SUPPORTED_EXTENSIONS:
        raise FileDetectionError("The content has no recognized file signature and its text extension is unsupported.")
    return suffix


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
    table = _table_rows([[cell.strip() for cell in row] for row in rows])
    if not table:
        return None
    text = "\n".join(row.quote() for row in table)
    return ParsedDocument(pages=[ParsedPage(1, text, "native", table_rows=table)], fidelity_tier="structural", page_count=1)


def _table_rows(rows: list[list[str]], sheet_name: str | None = None) -> list[TableRow]:
    populated = [(number, cells) for number, cells in enumerate(rows, 1) if any(cells)]
    if not populated:
        return []
    header_number, headers = populated[0]
    # Retain every column, including empty cells. Ragged rows must not shift values.
    width = max(len(cells) for _, cells in populated)
    headers = headers + [""] * (width - len(headers))
    return [TableRow(headers=headers, cells=cells + [""] * (width - len(cells)),
                     sheet_name=sheet_name, row_number=number,
                     data_row_count=len(populated) - 1, is_header=number == header_number)
            for number, cells in populated]


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
        blocks, page_count = read_docx(payload)
    except (ElementTree.ParseError, KeyError, OSError, zipfile.BadZipFile):
        return None
    pages: list[ParsedPage] = []
    for number in range(1, page_count + 1):
        page_blocks = [block for block in blocks if block.page == number]
        text = "\n\n".join(block.text for block in page_blocks)
        if text:
            pages.append(ParsedPage(number, text, "native", docx_blocks=page_blocks))
    if not pages:
        return None
    return ParsedDocument(pages=pages, fidelity_tier="structural", page_count=page_count)


def parse_xlsx(payload: bytes) -> ParsedDocument | None:
    if openpyxl is None:  # pragma: no cover
        return None
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    except Exception:
        return None
    pages: list[ParsedPage] = []
    for index, sheet in enumerate(workbook.worksheets, start=1):
        rows: list[list[str]] = []
        for row in sheet.iter_rows():
            cells: list[str] = []
            for cell in row:
                value = cell.value
                if isinstance(value, (int, float)) and "%" in cell.number_format:
                    cells.append(f"{Decimal(str(value)) * 100}%")
                elif isinstance(value, (int, float)) and re.search(r"[$€£₹¥]", cell.number_format):
                    symbol = re.search(r"[$€£₹¥]", cell.number_format)[0]
                    cells.append(f"{symbol}{value}")
                else:
                    cells.append("" if value is None else str(value).strip())
            rows.append(cells)
        table = _table_rows(rows, sheet.title)
        if table:
            pages.append(ParsedPage(index, "\n".join(row.quote() for row in table), "native", table_rows=table))
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
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in paragraph.runs).strip()
                    if line:
                        lines.append(line)
            # PowerPoint tables are represented as table shapes, not text
            # frames, and were silently skipped by the previous parser.
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    line = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
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

    # Fidelity must reflect whether OCR was *needed*, not whether it happened
    # to succeed. A page queued for OCR that recognizes nothing falls back to
    # its own sparse native text (below ocr_min_chars_per_page -- that sparse
    # text is why it was queued in the first place) tagged source="native". If
    # every scanned page in a document does this, `any(page.source == "ocr")`
    # would report the whole document as "full_layout" -- claiming more
    # precision than the parser actually delivered (invariant 1).
    ocr_used = bool(scan_numbers)
    return ParsedDocument(
        pages=pages,
        fidelity_tier="ocr_dependent" if ocr_used else "full_layout",
        page_count=len(pages),
        ocr_engine=engine.name if ocr_used else None,
    )
