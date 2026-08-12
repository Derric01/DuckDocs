"""Document upload, listing, ingest jobs, page previews, and the raw file."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import RagDep, RepositoryDep, SettingsDep
from app.core.errors import DuckDocsError
from app.domain.models import Document, IngestJob, PaginatedDocuments, UploadItem, UploadResponse, utc_now
from app.services.ingest import process_ingest, stored_file_path
from app.services.parsing import (
    CODE_EXTENSIONS,
    IMAGE_EXTENSIONS,
    PLAIN_TEXT_EXTENSIONS,
    STRUCTURED_TEXT_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    probe_page_count,
)
from app.services.preview import render_image_page, render_pdf_page

router = APIRouter(tags=["documents"])

# Types the browser can render directly, so opening the real file is worth
# doing inline (a new tab, not a download prompt). Two deliberate exclusions:
#   - TIFF has no native browser renderer, so inline would just show a blank
#     tab; it downloads instead, same as the office formats.
#   - HTML is excluded even though browsers render it -- a stored HTML upload
#     served inline from this origin would execute any script it contains
#     (stored XSS). It always downloads, regardless of what it actually is.
_INLINE_SAFE_EXTENSIONS = (
    {"pdf", "png", "jpg", "jpeg", "webp", "bmp", "csv"}
    | CODE_EXTENSIONS
    | STRUCTURED_TEXT_EXTENSIONS
    | PLAIN_TEXT_EXTENSIONS
)


@router.get("/documents", response_model=PaginatedDocuments)
async def list_documents(
    repo: RepositoryDep,
    limit: int = Query(default=25, ge=1, le=100),
    status: str | None = None,
) -> PaginatedDocuments:
    documents = repo.list_documents()
    if status:
        documents = [document for document in documents if document.status == status]
    return PaginatedDocuments(items=documents[:limit], has_more=len(documents) > limit)


@router.get("/documents/{document_id}", response_model=Document)
async def get_document(document_id: str, repo: RepositoryDep) -> Document:
    document = repo.get_document(document_id)
    if document is None:
        raise DuckDocsError("not_found", "Document was not found.", 404)
    return document


@router.get("/documents/{document_id}/file")
async def document_file(document_id: str, repo: RepositoryDep, runtime: SettingsDep) -> FileResponse:
    """The real, original file -- not a re-rendered page image.

    The source panel's page view is a rasterized image so it can draw the
    citation bounding box on top of it, which is genuinely useful and worth
    keeping. But a raster is not the document: it has no selectable text, no
    real fonts, and formats with no page-image concept at all (DOCX, XLSX,
    PPTX) have no visual representation there whatsoever. This serves the
    actual stored bytes so the browser's own viewer -- or, for formats it
    can't render, the OS's default handler -- opens the real thing.

    Starlette's FileResponse answers Range requests itself (206 Partial
    Content), which is what lets a browser's built-in PDF viewer page through
    a large file without pulling the whole thing up front.
    """
    document = repo.get_document(document_id)
    if document is None:
        raise DuckDocsError("not_found", "Document was not found.", 404)

    file_path = stored_file_path(runtime, document_id, document.name)
    if not file_path.exists():
        raise DuckDocsError(
            "not_found",
            "The stored file for this document is missing.",
            404,
            "Upload the file again.",
        )

    media_type = document.mime_type if "/" in document.mime_type else None
    media_type = media_type or mimetypes.guess_type(document.name)[0] or "application/octet-stream"
    disposition = "inline" if document.file_type in _INLINE_SAFE_EXTENSIONS else "attachment"

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=document.name,
        content_disposition_type=disposition,
        headers={
            # The browser must render exactly what was declared, never sniff
            # a stored upload into something more dangerous than its extension.
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/documents", response_model=UploadResponse, status_code=201)
async def upload_documents(
    files: Annotated[list[UploadFile], File(...)],
    background_tasks: BackgroundTasks,
    repo: RepositoryDep,
    runtime: SettingsDep,
    rag: RagDep,
) -> UploadResponse:
    if not files:
        raise DuckDocsError("validation_error", "Choose at least one file to add.", 400)

    items: list[UploadItem] = []
    for file in files:
        suffix = Path(file.filename or "").suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_EXTENSIONS:
            raise DuckDocsError(
                "unsupported_file_type",
                f".{suffix or 'file'} is not supported.",
                415,
                "Choose PDF, Office documents, spreadsheets, presentations, images, or text/code files.",
            )
        payload = await file.read()
        if len(payload) > runtime.max_file_size:
            raise DuckDocsError("file_too_large", f"{file.filename} exceeds the 50 MB upload limit.", 413)

        document_id = f"doc_{uuid4().hex[:12]}"
        now = utc_now()
        document = Document(
            id=document_id,
            name=file.filename or "Untitled file",
            file_type=suffix,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=len(payload),
            status="processing",
            fidelity_tier="ocr_dependent" if suffix in IMAGE_EXTENSIONS else "structural",
            # Structural page count, so the preview can page through the file
            # even if extraction later yields nothing.
            pages=probe_page_count(payload, suffix),
            category="New upload",
            current_version_id=f"ver_{uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
        )
        job_id = f"job_{uuid4().hex[:12]}"
        job = IngestJob(
            id=job_id,
            document_id=document_id,
            status="queued",
            stage="queued",
            progress_pct=0,
            created_at=now,
            updated_at=now,
        )

        target = stored_file_path(runtime, document_id, document.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        repo.add_document(document, job)

        # Parsing (including OCR) is deferred entirely to the background task
        # so a large scanned upload never blocks the HTTP response.
        background_tasks.add_task(process_ingest, repo, rag, runtime, document_id, job_id, payload, suffix)
        items.append(UploadItem(document=document, ingest_job_id=job_id))

    return UploadResponse(items=items)


@router.post("/documents/{document_id}/retry", response_model=IngestJob, status_code=202)
async def retry_ingest(
    document_id: str,
    background_tasks: BackgroundTasks,
    repo: RepositoryDep,
    runtime: SettingsDep,
    rag: RagDep,
) -> IngestJob:
    """Re-run ingestion from the stored file.

    The reconciler fails jobs orphaned by a restart, so this is the path back
    for them as well as for genuine parse failures.
    """
    document = repo.get_document(document_id)
    if document is None:
        raise DuckDocsError("not_found", "Document was not found.", 404)

    path = stored_file_path(runtime, document_id, document.name)
    if not path.exists():
        raise DuckDocsError(
            "not_found",
            "The stored file for this document is missing, so it cannot be reprocessed.",
            404,
            "Upload the file again.",
        )

    payload = await asyncio.to_thread(path.read_bytes)
    now = utc_now()
    job = IngestJob(
        id=f"job_{uuid4().hex[:12]}",
        document_id=document_id,
        status="queued",
        stage="queued",
        progress_pct=0,
        created_at=now,
        updated_at=now,
    )
    repo.add_job(job)
    repo.update_document(document_id, status="processing")

    background_tasks.add_task(
        process_ingest, repo, rag, runtime, document_id, job.id, payload, document.file_type
    )
    return job


@router.get("/documents/{document_id}/status", response_model=IngestJob)
async def document_status(document_id: str, repo: RepositoryDep) -> IngestJob:
    jobs = [job for job in repo.jobs.values() if job.document_id == document_id]
    if not jobs:
        raise DuckDocsError("not_found", "Ingest job was not found.", 404)
    return jobs[-1]


@router.get("/ingest-jobs", response_model=list[IngestJob])
async def list_jobs(repo: RepositoryDep) -> list[IngestJob]:
    return list(repo.jobs.values())


@router.get("/documents/{document_id}/pages/{page}/image")
async def document_page_image(
    document_id: str,
    page: int,
    repo: RepositoryDep,
    runtime: SettingsDep,
    dpi: int = Query(default=144, ge=48, le=400),
) -> Response:
    """Rasterized page image for the preview panel.

    Only PDF and image formats have a page-image concept; other formats
    return 404 with a stable reason code so the frontend can fall back to
    the text passage view instead of showing a broken image.
    """
    document = repo.get_document(document_id)
    if document is None:
        raise DuckDocsError("not_found", "Document was not found.", 404)
    if page < 1 or page > document.pages:
        raise DuckDocsError("not_found", f"Page {page} is out of range for this document.", 404)

    file_path = stored_file_path(runtime, document_id, document.name)
    if not file_path.exists():
        raise DuckDocsError("not_found", "The stored file for this document is missing.", 404)

    suffix = document.file_type
    if suffix == "pdf":
        image_bytes = await asyncio.to_thread(render_pdf_page, file_path, page, dpi)
    elif suffix in IMAGE_EXTENSIONS:
        image_bytes = await asyncio.to_thread(render_image_page, file_path.read_bytes(), page)
    else:
        raise DuckDocsError(
            "preview_unavailable",
            f".{suffix} files do not have a page preview.",
            404,
            "View the extracted passage in the evidence panel instead.",
        )

    if image_bytes is None:
        raise DuckDocsError("preview_unavailable", "This page could not be rendered.", 404)

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
