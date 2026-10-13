import io
import zipfile

import openpyxl
import pytest

from app.core.config import Settings
from app.services.parsing import FileDetectionError, detect_file_type, parse_upload
from tests.test_ingestion import _native_pdf_bytes, client_with_data_root
from tests.test_phase5_answers import ask, upload


def workbook_bytes():
    workbook = openpyxl.Workbook()
    workbook.active.title = "Counts"
    workbook.active.append(["Product", "Units"])
    workbook.active.append(["Cog", 27])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_workbook_renamed_csv_is_parsed_and_cited_as_excel(tmp_path):
    payload = workbook_bytes()
    assert detect_file_type(payload, "csv") == "xlsx"
    parsed = parse_upload(payload, "csv", Settings())
    assert parsed.pages[0].table_rows[1].cells == ["Cog", "27"]
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "renamed.csv", payload)
        metadata = client.get(f"/api/v1/documents/{doc}").json()
        assert metadata["file_type"] == "xlsx"
        assert metadata["mime_type"].endswith("spreadsheetml.sheet")
        assert metadata["status"] == "ready"
        assert metadata["name"] == "renamed.csv"
        original = client.get(f"/api/v1/documents/{doc}/file")
        assert original.content == payload
        assert original.headers["content-disposition"].startswith("attachment")
        assert ask(client, "Sum Units in Excel", doc)["answer"] == "Units: 27 = 27"
        assert not ask(client, "Sum Units in CSV", doc)["grounded"]
        assert ask(client, "Sum Units in renamed.csv", doc)["grounded"]


def test_pdf_magic_overrides_unknown_extension(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "paper.bin", _native_pdf_bytes("Local archive includes a readable synthetic paragraph."))
        assert client.get(f"/api/v1/documents/{doc}").json()["file_type"] == "pdf"


@pytest.mark.parametrize("payload,suffix,message", [
    (b"PK\x03\x04bad archive", "csv", "corrupt"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1more", "xls", "Legacy"),
    (b"hello plain text", "xlsx", "plain text"),
    (b"\x00\x01\xff", "csv", "binary"),
])
def test_unrecognized_content_has_clear_upload_error(tmp_path, payload, suffix, message):
    with client_with_data_root(tmp_path) as client:
        result = client.post("/api/v1/documents", files={"files": (f"bad.{suffix}", payload)})
        assert result.status_code == 415
        assert result.json()["error"]["code"] == "unsupported_file_content"
        assert message in result.json()["error"]["message"]
        assert client.get("/api/v1/documents").json()["items"] == []


def test_generic_zip_is_not_mistaken_for_workbook():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "ordinary zip contents")
    with pytest.raises(FileDetectionError, match="not an unambiguous"):
        detect_file_type(buffer.getvalue(), "xlsx")


def test_retry_detects_content_again_and_reports_bad_stored_content(tmp_path):
    from app.api.dependencies import get_repository
    from app.main import app
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "renamed.csv", workbook_bytes())
        repo = app.dependency_overrides[get_repository]()
        repo.update_document(doc, file_type="csv", mime_type="text/csv")
        result = client.post(f"/api/v1/documents/{doc}/retry")
        assert result.status_code == 202
        assert client.get(f"/api/v1/documents/{doc}").json()["file_type"] == "xlsx"
        # The test's own isolated stored file is corrupted to exercise retry errors.
        (tmp_path / "documents" / doc / "renamed.csv").write_bytes(b"\x00bad")
        result = client.post(f"/api/v1/documents/{doc}/retry")
        job = next(job for job in client.get("/api/v1/ingest-jobs").json() if job["id"] == result.json()["id"])
        assert job["error"]["reason_code"] == "unsupported_file_content"
        assert "binary" in job["error"]["human_message"]
        assert not ask(client, "Sum Units", doc)["grounded"]
