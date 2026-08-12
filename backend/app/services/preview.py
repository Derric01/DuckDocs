"""On-demand page rendering for the document preview UI.

Pages are rasterized at request time rather than pre-rendered and stored: the
source file already lives on disk, so this trades a little CPU per request for
no extra storage and no staleness risk. Responses carry a long immutable
Cache-Control header, since a given (document, page, dpi) never changes once
ingested.

Opened PDFs are cached. `fitz.open` parses the whole file, so without a cache
every page turn would re-parse the document — on a large PDF that dominates
the request. The cache is bounded and keyed on path plus mtime and size, so an
edited or replaced file is never served from a stale handle.
"""

from __future__ import annotations

import io
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

# Each entry holds an open PyMuPDF document. Small on purpose: a handful of
# handles covers realistic paging while bounding memory on big files.
MAX_CACHED_DOCUMENTS = 4

_CacheKey = tuple[str, float, int]
_cache: OrderedDict[_CacheKey, Any] = OrderedDict()
# PyMuPDF document objects are not thread-safe, and preview requests run in a
# thread pool, so all access is serialized.
_lock = threading.Lock()


def _cache_key(path: Path) -> _CacheKey | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path), stat.st_mtime, stat.st_size)


def _evict_locked() -> None:
    while len(_cache) > MAX_CACHED_DOCUMENTS:
        _, document = _cache.popitem(last=False)
        try:
            document.close()
        except Exception:
            pass


def clear_preview_cache() -> None:
    """Close and drop every cached document. Used by tests and on shutdown."""
    with _lock:
        while _cache:
            _, document = _cache.popitem()
            try:
                document.close()
            except Exception:
                pass


def preview_cache_size() -> int:
    with _lock:
        return len(_cache)


def render_pdf_page(path: Path, page_number: int, dpi: int) -> bytes | None:
    """Rasterize one PDF page to PNG bytes, or None if it can't be rendered."""
    if fitz is None:  # pragma: no cover
        return None

    key = _cache_key(path)
    if key is None:
        return None

    with _lock:
        document = _cache.get(key)
        if document is None:
            try:
                document = fitz.open(path)
            except Exception:
                return None
            _cache[key] = document
            _evict_locked()
        else:
            _cache.move_to_end(key)

        try:
            if page_number < 1 or page_number > document.page_count:
                return None
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(dpi=dpi)
            result: bytes = pixmap.tobytes("png")
            return result
        except Exception:
            # A document that fails mid-render may be corrupt; drop the handle
            # rather than serving errors from it forever.
            _cache.pop(key, None)
            try:
                document.close()
            except Exception:
                pass
            return None


def render_pdf_page_from_bytes(payload: bytes, page_number: int, dpi: int) -> bytes | None:
    """Render from an in-memory PDF. Used where no stored path exists."""
    if fitz is None:  # pragma: no cover
        return None
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return None
    try:
        if page_number < 1 or page_number > document.page_count:
            return None
        pixmap = document.load_page(page_number - 1).get_pixmap(dpi=dpi)
        result: bytes = pixmap.tobytes("png")
        return result
    except Exception:
        return None
    finally:
        document.close()


def render_image_page(payload: bytes, page_number: int) -> bytes | None:
    """Return one frame of an image file as PNG bytes."""
    if Image is None:  # pragma: no cover
        return None
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception:
        return None

    frame_count = int(getattr(image, "n_frames", 1) or 1)
    if page_number < 1 or page_number > frame_count:
        return None

    try:
        if frame_count > 1:
            # ImageSequence.Iterator yields the *same* object seeked to each
            # position, so materializing it into a list and indexing later
            # would return the final frame every time. Seek, then convert.
            image.seek(page_number - 1)
        frame = image.convert("RGB")
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:
        return None
