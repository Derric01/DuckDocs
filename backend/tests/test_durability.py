"""Ingest durability, retry, and preview caching."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.api.dependencies import get_registry, get_repository, get_runtime_settings, get_vector_store
from app.core.config import Settings
from app.domain.models import Document, IngestJob, utc_now
from app.main import app
from app.repositories.memory import DocumentRepository
from app.services.ingest import reconcile_orphaned_jobs
from app.services.ocr import RapidOcrEngine
from app.services.preview import (
    clear_preview_cache,
    preview_cache_size,
    render_pdf_page,
)
from tests.test_ingestion import _native_pdf_bytes, client_with_data_root


def _document(document_id: str, status: str = "processing") -> Document:
    now = utc_now()
    return Document(
        id=document_id,
        name="policy.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        status=status,  # type: ignore[arg-type]
        fidelity_tier="structural",
        pages=1,
        category="New upload",
        current_version_id="ver_1",
        created_at=now,
        updated_at=now,
    )


def _job(job_id: str, document_id: str, status: str, stage: str) -> IngestJob:
    now = utc_now()
    return IngestJob(
        id=job_id,
        document_id=document_id,
        status=status,  # type: ignore[arg-type]
        stage=stage,  # type: ignore[arg-type]
        progress_pct=40,
        created_at=now,
        updated_at=now,
    )


# --- orphan reconciliation ------------------------------------------------


def test_orphaned_running_jobs_are_failed_at_startup(tmp_path: Path) -> None:
    """A restart mid-ingest must not leave a job stuck on 'processing' forever."""
    repo = DocumentRepository(tmp_path)
    repo.add_document(_document("doc_a"), _job("job_a", "doc_a", "processing", "ocr"))

    recovered = reconcile_orphaned_jobs(repo)

    assert len(recovered) == 1
    job = repo.get_job("job_a")
    assert job is not None
    assert job.status == "failed"
    assert job.error is not None
    assert job.error["reason_code"] == "interrupted"
    # The message must tell the user what to do, not just that it broke.
    assert "retry" in job.error["human_message"].lower()
    # And the document must stop claiming work is in progress.
    document = repo.get_document("doc_a")
    assert document is not None
    assert document.status == "review"


def test_queued_jobs_are_also_reconciled(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    repo.add_document(_document("doc_b"), _job("job_b", "doc_b", "queued", "queued"))
    assert len(reconcile_orphaned_jobs(repo)) == 1


def test_finished_jobs_are_left_alone(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    repo.add_document(_document("doc_c", status="ready"), _job("job_c", "doc_c", "ready", "ready"))
    repo.add_document(_document("doc_d", status="review"), _job("job_d", "doc_d", "failed", "failed"))

    assert reconcile_orphaned_jobs(repo) == []
    ready = repo.get_job("job_c")
    assert ready is not None and ready.status == "ready"
    assert repo.get_document("doc_c").status == "ready"  # type: ignore[union-attr]


def test_reconciliation_is_idempotent(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    repo.add_document(_document("doc_e"), _job("job_e", "doc_e", "processing", "parsing"))
    assert len(reconcile_orphaned_jobs(repo)) == 1
    # A second startup must not re-fail an already-failed job.
    assert reconcile_orphaned_jobs(repo) == []


def test_reconciliation_survives_a_process_restart(tmp_path: Path) -> None:
    """State is on disk, so a fresh repository still sees the orphan."""
    first = DocumentRepository(tmp_path)
    first.add_document(_document("doc_f"), _job("job_f", "doc_f", "processing", "embedding"))

    reopened = DocumentRepository(tmp_path)
    assert len(reconcile_orphaned_jobs(reopened)) == 1


# --- retry ----------------------------------------------------------------


def test_retry_reprocesses_a_document_from_the_stored_file(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"files": ("native.pdf", _native_pdf_bytes("Retention rules apply for eighteen months."), "application/pdf")},
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        response = client.post(f"/api/v1/documents/{document_id}/retry")
        assert response.status_code == 202
        assert response.json()["document_id"] == document_id

        document = client.get(f"/api/v1/documents/{document_id}").json()
        assert document["status"] == "ready"

    app.dependency_overrides.clear()


def test_retry_on_unknown_document_is_404(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        assert client.post("/api/v1/documents/doc_missing/retry").status_code == 404
    app.dependency_overrides.clear()


def test_retry_reports_a_missing_stored_file(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    repo.add_document(_document("doc_g", status="review"), _job("job_g", "doc_g", "failed", "failed"))
    runtime = Settings(data_root=tmp_path, chroma_url=None, db_url=None)

    from fastapi.testclient import TestClient

    from app.providers.registry import ProviderRegistry
    from app.services.vector_store import VectorStore

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_runtime_settings] = lambda: runtime
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry(
        runtime, config_path=tmp_path / "provider_configs.json"
    )
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(runtime)

    with TestClient(app) as client:
        response = client.post("/api/v1/documents/doc_g/retry")
        assert response.status_code == 404
        assert response.json()["error"]["suggested_action"]

    app.dependency_overrides.clear()


# --- preview cache --------------------------------------------------------


def test_pdf_pages_are_served_from_a_cached_handle(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(_native_pdf_bytes("Cached rendering test content here."))
    clear_preview_cache()

    first = render_pdf_page(path, 1, 96)
    assert first is not None
    assert preview_cache_size() == 1

    # A second request must reuse the handle rather than re-parsing the file.
    second = render_pdf_page(path, 1, 96)
    assert second == first
    assert preview_cache_size() == 1

    clear_preview_cache()
    assert preview_cache_size() == 0


def test_cache_is_bounded(tmp_path: Path) -> None:
    clear_preview_cache()
    for index in range(8):
        path = tmp_path / f"doc_{index}.pdf"
        path.write_bytes(_native_pdf_bytes(f"Document number {index} with enough body text."))
        assert render_pdf_page(path, 1, 72) is not None

    from app.services.preview import MAX_CACHED_DOCUMENTS

    assert preview_cache_size() <= MAX_CACHED_DOCUMENTS
    clear_preview_cache()


def test_rewriting_a_file_invalidates_its_cached_handle(tmp_path: Path) -> None:
    """The key includes mtime and size, so a replaced file is never stale."""
    path = tmp_path / "doc.pdf"
    path.write_bytes(_native_pdf_bytes("First version of the document body."))
    clear_preview_cache()
    first = render_pdf_page(path, 1, 72)

    import os
    import time

    time.sleep(0.01)
    path.write_bytes(_native_pdf_bytes("A completely different second version of the body."))
    os.utime(path, (time.time() + 1, time.time() + 1))

    second = render_pdf_page(path, 1, 72)
    assert second is not None
    assert second != first

    clear_preview_cache()


def test_render_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    assert render_pdf_page(tmp_path / "nope.pdf", 1, 96) is None


# --- rapidocr engine ------------------------------------------------------


def test_rapidocr_parses_the_documented_result_shape() -> None:
    engine = RapidOcrEngine("eng")
    raw = [
        [[[10, 10], [110, 10], [110, 30], [10, 30]], "Retention window", 0.98],
        [[[10, 40], [90, 40], [90, 60], [10, 60]], "eighteen months", 0.90],
    ]
    result = engine._parse(raw, width=200, height=100)

    assert result.engine == "rapidocr"
    assert result.text == "Retention window\neighteen months"
    assert result.confidence is not None and 0.93 < result.confidence < 0.95
    assert result.lines[0].bbox is not None
    assert result.envelope is not None


def test_rapidocr_handles_a_blank_page() -> None:
    assert RapidOcrEngine("eng")._parse(None, 100, 100).text == ""
    assert RapidOcrEngine("eng")._parse([], 100, 100).text == ""


def test_rapidocr_skips_malformed_entries() -> None:
    engine = RapidOcrEngine("eng")
    raw = [
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "kept", 0.9],
        ["not-an-entry"],
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "   ", 0.9],
    ]
    assert engine._parse(raw, 100, 100).text == "kept"


def test_rapidocr_recognizes_a_real_image() -> None:
    """The bundled weights mean this needs no download, unlike PaddleOCR."""
    engine = RapidOcrEngine("eng")
    if not engine.available():  # pragma: no cover - depends on the wheel
        import pytest

        pytest.skip("rapidocr-onnxruntime not installed")

    from tests.test_ingestion import _render_text_image

    result = engine.recognize(_render_text_image("Northwind lease renewal"), "eng")
    assert result.engine == "rapidocr"
    assert "Northwind" in result.text or "lease" in result.text.lower()
    assert result.confidence is not None
    assert result.lines and result.lines[0].bbox is not None


def test_rapidocr_batch_matches_input_length() -> None:
    engine = RapidOcrEngine("eng")
    if not engine.available():  # pragma: no cover
        import pytest

        pytest.skip("rapidocr-onnxruntime not installed")
    images = [Image.new("RGB", (80, 40), "white") for _ in range(3)]
    assert len(engine.recognize_batch(images, "eng")) == 3
