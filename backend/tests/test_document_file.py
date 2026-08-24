"""GET /documents/{id}/file -- the real original bytes, not a rasterized page.

The page-image endpoint (test_ingestion.py, test_preview.py) covers the
rendered view. This covers the source panel's "open the real document"
escape hatch: the actual stored file, byte-for-byte, with Range support so a
browser's native PDF viewer can page through a large document.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_ingestion import _native_pdf_bytes, client_with_data_root


def test_serves_the_exact_original_bytes(tmp_path: Path) -> None:
    payload = _native_pdf_bytes("Retention window is eighteen months.")
    with client_with_data_root(tmp_path) as client:
        document_id = client.post(
            "/api/v1/documents",
            files={"files": ("policy.pdf", payload, "application/pdf")},
        ).json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/file")
        assert response.status_code == 200
        assert response.content == payload
        assert response.headers["content-type"] == "application/pdf"
        assert 'filename="policy.pdf"' in response.headers["content-disposition"]
        # Inline, not a download prompt: the browser's own PDF viewer should
        # open it directly.
        assert response.headers["content-disposition"].startswith("inline")
        assert response.headers["x-content-type-options"] == "nosniff"


def test_supports_range_requests_for_the_native_pdf_viewer(tmp_path: Path) -> None:
    payload = _native_pdf_bytes("Range support matters for large scanned PDFs.")
    with client_with_data_root(tmp_path) as client:
        document_id = client.post(
            "/api/v1/documents",
            files={"files": ("policy.pdf", payload, "application/pdf")},
        ).json()["items"][0]["document"]["id"]

        response = client.get(
            f"/api/v1/documents/{document_id}/file",
            headers={"Range": "bytes=0-9"},
        )
        assert response.status_code == 206
        assert response.content == payload[:10]
        assert response.headers["content-range"] == f"bytes 0-9/{len(payload)}"


def test_opaque_office_formats_download_rather_than_render_blank(tmp_path: Path) -> None:
    """DOCX has no browser renderer; a download is honest, an inline blank tab is not."""
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={
                "files": (
                    "memo.docx",
                    b"PK\x03\x04not a real docx but the router only looks at metadata",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/file")
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment")


def test_html_is_never_served_inline_even_though_browsers_can_render_it(tmp_path: Path) -> None:
    """A stored HTML upload served inline from this origin would execute its script -- stored XSS."""
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"files": ("notes.html", b"<html><body>hello</body></html>", "text/html")},
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.get(f"/api/v1/documents/{document_id}/file")
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment")


def test_unknown_document_is_404(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        assert client.get("/api/v1/documents/doc_missing/file").status_code == 404


def test_missing_stored_file_is_404_not_a_crash(tmp_path: Path) -> None:
    payload = _native_pdf_bytes("This file will be deleted out from under the document row.")
    with client_with_data_root(tmp_path) as client:
        document_id = client.post(
            "/api/v1/documents",
            files={"files": ("policy.pdf", payload, "application/pdf")},
        ).json()["items"][0]["document"]["id"]

        stored = tmp_path / "documents" / document_id / "policy.pdf"
        assert stored.exists()
        stored.unlink()

        response = client.get(f"/api/v1/documents/{document_id}/file")
        assert response.status_code == 404
        assert response.json()["error"]["suggested_action"]
