"""On-demand page rendering for the document preview UI.

Pages are rasterized at request time rather than pre-rendered and stored:
the source file already lives on disk, so this trades a small amount of CPU
per request for zero extra storage and zero staleness risk if a document's
stored version ever changes. Responses are served with a long, immutable
Cache-Control header since a given (document, page, dpi) triple never
changes once a document has been ingested.
"""

from __future__ import annotations

import io

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]


def render_pdf_page(payload: bytes, page_number: int, dpi: int) -> bytes | None:
    """Rasterize one PDF page to PNG bytes, or None if it can't be rendered."""
    if fitz is None:  # pragma: no cover
        return None
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return None
    try:
        if page_number < 1 or page_number > document.page_count:
            return None
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(dpi=dpi)
        result: bytes = pixmap.tobytes("png")
        return result
    except Exception:
        return None
    finally:
        document.close()


def render_image_page(payload: bytes, page_number: int) -> bytes | None:
    """Return one frame of an image file as PNG bytes (frame 1 for single-frame images)."""
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
