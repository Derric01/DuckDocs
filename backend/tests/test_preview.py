"""Page-image preview endpoint tests.

The preview panel needs a real rendered page, not just extracted text, so
these exercise the actual PyMuPDF/Pillow rendering path end to end rather
than mocking it.
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image

from app.main import app
from tests.test_ingestion import _native_pdf_bytes, _scanned_pdf_bytes, client_with_data_root


def _multi_frame_tiff_bytes() -> bytes:
    frames = [Image.new("RGB", (60, 40), color) for color in ("red", "green", "blue")]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="TIFF", save_all=True, append_images=frames[1:])
    return buffer.getvalue()


def test_pdf_page_renders_as_png(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents", files={"files": ("native.pdf", _native_pdf_bytes("Some readable content here."), "application/pdf")}
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["cache-control"].startswith("public")
        # Must actually be a valid, non-trivial PNG.
        image = Image.open(io.BytesIO(response.content))
        assert image.format == "PNG"
        assert image.width > 10 and image.height > 10

    app.dependency_overrides.clear()


def test_scanned_pdf_page_renders_too(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents", files={"files": ("scan.pdf", _scanned_pdf_bytes("Preview test"), "application/pdf")}
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/pages/1/image?dpi=96")
        assert response.status_code == 200
        assert Image.open(io.BytesIO(response.content)).format == "PNG"

    app.dependency_overrides.clear()


def test_multi_page_pdf_each_page_renders_distinctly(tmp_path: Path) -> None:
    document = fitz.open()
    for index in range(3):
        page = document.new_page()
        page.insert_text((72, 72), f"Page number {index + 1}", fontsize=24)
    payload = document.tobytes()

    with client_with_data_root(tmp_path) as client:
        upload = client.post("/api/v1/documents", files={"files": ("multi.pdf", payload, "application/pdf")})
        document_id = upload.json()["items"][0]["document"]["id"]

        page1 = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        page2 = client.get(f"/api/v1/documents/{document_id}/pages/2/image")
        assert page1.status_code == 200
        assert page2.status_code == 200
        assert page1.content != page2.content

        out_of_range = client.get(f"/api/v1/documents/{document_id}/pages/4/image")
        assert out_of_range.status_code == 404

    app.dependency_overrides.clear()


def test_image_document_page_renders(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, format="PNG")

    with client_with_data_root(tmp_path) as client:
        upload = client.post("/api/v1/documents", files={"files": ("photo.png", buffer.getvalue(), "image/png")})
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        assert response.status_code == 200
        assert Image.open(io.BytesIO(response.content)).size == (200, 100)

    app.dependency_overrides.clear()


def test_multi_frame_tiff_serves_each_frame(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents", files={"files": ("scan.tiff", _multi_frame_tiff_bytes(), "image/tiff")}
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        page1 = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        page2 = client.get(f"/api/v1/documents/{document_id}/pages/2/image")
        assert page1.status_code == 200
        assert page2.status_code == 200
        assert page1.content != page2.content

    app.dependency_overrides.clear()


def test_unsupported_format_returns_404_with_actionable_message(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"files": ("note.md", b"# Title\n\nEnough alphanumeric content to pass the extraction floor.", "text/markdown")},
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "preview_unavailable"
        assert body["error"]["suggested_action"]

    app.dependency_overrides.clear()


def test_unknown_document_returns_404(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        response = client.get("/api/v1/documents/doc_missing/pages/1/image")
        assert response.status_code == 404

    app.dependency_overrides.clear()
