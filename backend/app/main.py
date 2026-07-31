"""FastAPI application for DuckDocs.

Implements the P0 API seam in docs/15_API_SPECIFICATION.md, the local health
contract in docs/31_OBSERVABILITY.md, and the honest refusal path in
docs/33_ERROR_HANDLING.md. Provider adapters attach when reachable; otherwise
the offline extractive/keyword path remains active.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Annotated
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response

from app.core.config import Settings, settings
from app.core.errors import DuckDocsError, duckdocs_error_handler
from app.domain.models import (
    AskRequest,
    Document,
    GroundedResponse,
    IngestJob,
    PaginatedDocuments,
    Provider,
    ProviderConfigRequest,
    ProviderConfigResponse,
    ProviderTestResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SettingsResponse,
    UploadItem,
    UploadResponse,
    utc_now,
)
from app.providers.registry import ProviderRegistry
from app.providers.secrets import SecretStore
from app.repositories import AnyRepository
from app.repositories.sql import build_repository
from app.services.chunking import AnchorQuality, chunk_document
from app.services.ocr import build_engine
from app.services.parsing import (
    IMAGE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    ParsedDocument,
    parse_upload,
    probe_page_count,
)
from app.services.preview import render_image_page, render_pdf_page
from app.services.rag import RagService
from app.services.vector_store import VectorStore


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_root.mkdir(parents=True, exist_ok=True)
    (settings.data_root / "documents").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.add_exception_handler(DuckDocsError, duckdocs_error_handler)
_frontend_origins = {
    settings.frontend_origin,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_frontend_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = build_repository(settings.data_root, settings.db_url)
provider_registry = ProviderRegistry(settings)
secret_store = SecretStore(settings.data_root)
vector_store = VectorStore(settings)
started_at = monotonic()


def _anchor_quality_for(suffix: str, parsed: ParsedDocument) -> AnchorQuality:
    if suffix == "xlsx":
        return "cell"
    if parsed.fidelity_tier == "structural":
        return "line"
    return "paragraph"


@app.middleware("http")
async def local_auth_and_correlation(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Enforce optional local bearer auth and propagate a correlation id."""
    request_id = request.headers.get("X-Correlation-Id", f"req_{uuid4().hex[:16]}")
    if settings.api_token and request.url.path.startswith(settings.api_prefix):
        if request.headers.get("Authorization") != f"Bearer {settings.api_token}":
            unauthorized_response = JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "A local API token is required.",
                        "retryable": False,
                        "correlation_id": request_id,
                        "details": {},
                    }
                },
            )
            unauthorized_response.headers["X-Correlation-Id"] = request_id
            return unauthorized_response
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = request_id
    return response


def get_repository() -> AnyRepository:
    return repository


def get_runtime_settings() -> Settings:
    return settings


def get_registry() -> ProviderRegistry:
    return provider_registry


def get_vector_store() -> VectorStore:
    return vector_store


def get_secrets() -> SecretStore:
    return secret_store


def get_rag(
    repo: Annotated[AnyRepository, Depends(get_repository)],
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
    runtime: Annotated[Settings, Depends(get_runtime_settings)],
) -> RagService:
    return RagService(runtime, repo, registry, store)


def correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id", f"req_{uuid4().hex[:16]}")


def _provider_local(provider_type: str) -> bool:
    return provider_type in {"ollama", "extractive", "keyword"}


def _provider_display_name(provider_type: str) -> str:
    return {
        "ollama": "Ollama",
        "extractive": "DuckDocs Extractive",
        "keyword": "Keyword index",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
        "openai_compatible": "OpenAI-compatible",
    }.get(provider_type, provider_type)


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "version": settings.version, "uptime_s": round(monotonic() - started_at, 2)}


@app.get("/ready")
async def ready(
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> dict[str, object]:
    snapshot = registry.status_snapshot()
    metadata_store = "postgres" if settings.db_url else "json"
    ocr_engine = build_engine(settings)
    return {
        "status": "ready",
        "checks": {
            "metadata_store": metadata_store,
            "file_store": "ok",
            "vector_store": store.health(),
            "ocr_engine": ocr_engine.name,
            "ocr_ready": ocr_engine.available(),
            "ollama": "ok" if snapshot["chat"]["provider_type"] == "ollama" and snapshot["chat"]["connected"] else "optional",
            "chat_provider": f"{snapshot['chat']['provider_type']}:{snapshot['chat']['model']}",
            "embedding_provider": f"{snapshot['embedding']['provider_type']}:{snapshot['embedding']['model']}",
        },
    }


@app.get(f"{settings.api_prefix}/documents", response_model=PaginatedDocuments)
async def list_documents(
    repo: Annotated[AnyRepository, Depends(get_repository)],
    limit: int = Query(default=25, ge=1, le=100),
    status: str | None = None,
) -> PaginatedDocuments:
    documents = repo.list_documents()
    if status:
        documents = [document for document in documents if document.status == status]
    return PaginatedDocuments(items=documents[:limit], has_more=len(documents) > limit)


@app.get(f"{settings.api_prefix}/documents/{{document_id}}", response_model=Document)
async def get_document(document_id: str, repo: Annotated[AnyRepository, Depends(get_repository)]) -> Document:
    document = repo.get_document(document_id)
    if document is None:
        raise DuckDocsError("not_found", "Document was not found.", 404)
    return document


async def process_ingest(
    repo: AnyRepository,
    rag: RagService,
    runtime: Settings,
    document_id: str,
    job_id: str,
    payload: bytes,
    suffix: str,
) -> None:
    """Real ingestion: parse (with OCR fallback), chunk, embed, index.

    Parsing/OCR is CPU-bound and can take a while for large scanned PDFs, so
    it runs in a worker thread (`asyncio.to_thread`) rather than inline on
    the event loop -- the API stays responsive to health checks and other
    requests while a big document is being recognized.
    """
    repo.update_job(job_id, status="processing", stage="parsing", progress_pct=5)

    last_reported = 0

    def on_page(current: int, total: int) -> None:
        nonlocal last_reported
        if current != total and current - last_reported < 5:
            return
        last_reported = current
        progress_pct = 5 + int(55 * current / max(1, total))
        repo.update_job(job_id, status="processing", stage="ocr", progress_pct=min(progress_pct, 60))

    parsed = await asyncio.to_thread(parse_upload, payload, suffix, runtime, on_page)

    if parsed is None or not parsed.pages:
        repo.update_job(
            job_id,
            status="failed",
            stage="failed",
            progress_pct=100,
            error={
                "stage": "parsing",
                "reason_code": "no_extractable_content",
                "human_message": "DuckDocs could not find readable text in this file (via native parsing or OCR).",
            },
        )
        repo.update_document(document_id, status="review")
        return

    repo.update_job(job_id, status="processing", stage="chunking", progress_pct=65)
    anchor_quality = _anchor_quality_for(suffix, parsed)
    chunks = await asyncio.to_thread(chunk_document, parsed, runtime, anchor_quality)

    repo.update_job(job_id, status="processing", stage="embedding", progress_pct=80)
    indexed_count = repo.index_document_chunks(document_id, chunks, parsed.ocr_engine)

    if indexed_count:
        repo.update_job(job_id, status="processing", stage="indexing", progress_pct=92)
        await asyncio.to_thread(rag.index_document, document_id)

    # Keep the larger of the probed and parsed counts: a parser may skip pages
    # it found nothing on, but those pages still exist and are still previewable.
    existing = repo.get_document(document_id)
    page_count = max(parsed.page_count, existing.pages if existing else 1)

    repo.update_document(
        document_id,
        status="ready" if indexed_count else "review",
        fidelity_tier=parsed.fidelity_tier,
        pages=page_count,
    )
    repo.update_job(job_id, status="ready", stage="ready", progress_pct=100)


@app.post(f"{settings.api_prefix}/documents", response_model=UploadResponse, status_code=201)
async def upload_documents(
    files: Annotated[list[UploadFile], File(...)],
    background_tasks: BackgroundTasks,
    repo: Annotated[AnyRepository, Depends(get_repository)],
    runtime: Annotated[Settings, Depends(get_runtime_settings)],
    rag: Annotated[RagService, Depends(get_rag)],
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
        version_id = f"ver_{uuid4().hex[:12]}"
        job_id = f"job_{uuid4().hex[:12]}"
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
            current_version_id=version_id,
            created_at=now,
            updated_at=now,
        )
        job = IngestJob(
            id=job_id,
            document_id=document_id,
            status="queued",
            stage="queued",
            progress_pct=0,
            created_at=now,
            updated_at=now,
        )
        runtime.data_root.joinpath("documents", document_id).mkdir(parents=True, exist_ok=True)
        runtime.data_root.joinpath("documents", document_id, document.name).write_bytes(payload)
        repo.add_document(document, job)
        # Parsing (including OCR) is deferred entirely to the background task
        # so a large scanned upload never blocks the HTTP response.
        background_tasks.add_task(process_ingest, repo, rag, runtime, document_id, job_id, payload, suffix)
        items.append(UploadItem(document=document, ingest_job_id=job_id))
    return UploadResponse(items=items)


@app.get(f"{settings.api_prefix}/documents/{{document_id}}/status", response_model=IngestJob)
async def document_status(document_id: str, repo: Annotated[AnyRepository, Depends(get_repository)]) -> IngestJob:
    jobs = [job for job in repo.jobs.values() if job.document_id == document_id]
    if not jobs:
        raise DuckDocsError("not_found", "Ingest job was not found.", 404)
    return jobs[-1]


@app.get(f"{settings.api_prefix}/ingest-jobs", response_model=list[IngestJob])
async def list_jobs(repo: Annotated[AnyRepository, Depends(get_repository)]) -> list[IngestJob]:
    return list(repo.jobs.values())


@app.post(f"{settings.api_prefix}/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    rag: Annotated[RagService, Depends(get_rag)],
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
) -> SearchResponse:
    chunks = rag.retrieve(request.query, request.scope)
    embed = registry.get_embedding_provider()
    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(evidence=chunk.evidence, snippet=chunk.evidence.snippet, score=chunk.score)
            for chunk in chunks[: request.top_k]
        ],
        embedding_provider={"name": embed.ref["provider_type"], "model": embed.ref["model_name"]},
    )


@app.post(f"{settings.api_prefix}/ask", response_model=GroundedResponse)
async def ask(
    request: AskRequest,
    rag: Annotated[RagService, Depends(get_rag)],
) -> GroundedResponse:
    return rag.ask(request.query, request.scope)


@app.post(f"{settings.api_prefix}/ask/stream")
async def ask_stream(
    request: AskRequest,
    rag: Annotated[RagService, Depends(get_rag)],
) -> StreamingResponse:
    result, tokens = rag.ask_stream_tokens(request.query, request.scope)

    async def events() -> AsyncIterator[str]:
        for index, token in enumerate(tokens):
            yield f"event: token\ndata: {json.dumps({'index': index, 'text': token})}\n\n"
            await asyncio.sleep(0.01)
        yield f"event: done\ndata: {result.model_dump_json()}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get(f"{settings.api_prefix}/evidence/{{evidence_id}}")
async def get_evidence(evidence_id: str, repo: Annotated[AnyRepository, Depends(get_repository)]) -> object:
    item = repo.evidence.get(evidence_id)
    if item is None:
        raise DuckDocsError("not_found", "Evidence was not found.", 404)
    return item


@app.get(f"{settings.api_prefix}/documents/{{document_id}}/pages/{{page}}/image")
async def document_page_image(
    document_id: str,
    page: int,
    repo: Annotated[AnyRepository, Depends(get_repository)],
    runtime: Annotated[Settings, Depends(get_runtime_settings)],
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

    file_path = runtime.data_root / "documents" / document_id / document.name
    if not file_path.exists():
        raise DuckDocsError("not_found", "The stored file for this document is missing.", 404)

    suffix = document.file_type
    payload = await asyncio.to_thread(file_path.read_bytes)

    image_bytes: bytes | None = None
    if suffix == "pdf":
        image_bytes = await asyncio.to_thread(render_pdf_page, payload, page, dpi)
    elif suffix in IMAGE_EXTENSIONS:
        image_bytes = await asyncio.to_thread(render_image_page, payload, page)
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


@app.get(f"{settings.api_prefix}/providers", response_model=list[Provider])
async def providers(registry: Annotated[ProviderRegistry, Depends(get_registry)]) -> list[Provider]:
    items: list[Provider] = []
    for config in registry.list_configs():
        try:
            connected = registry.test_connectivity(config.id).reachable
        except Exception:
            connected = False
        items.append(
            Provider(
                id=config.id,
                kind=config.role,
                name=_provider_display_name(config.provider_type),
                model=config.model_name,
                configured=True,
                connected=connected,
                local=_provider_local(config.provider_type),
            )
        )
    return items


@app.get(f"{settings.api_prefix}/settings", response_model=SettingsResponse)
async def get_settings_endpoint(registry: Annotated[ProviderRegistry, Depends(get_registry)]) -> SettingsResponse:
    return SettingsResponse(providers=await providers(registry))


@app.get(f"{settings.api_prefix}/settings/providers", response_model=list[ProviderConfigResponse])
async def list_provider_configs(registry: Annotated[ProviderRegistry, Depends(get_registry)]) -> list[ProviderConfigResponse]:
    responses: list[ProviderConfigResponse] = []
    for config in registry.list_configs():
        try:
            connected = registry.test_connectivity(config.id).reachable
        except Exception:
            connected = False
        responses.append(
            ProviderConfigResponse(
                id=config.id,
                role=config.role,
                provider_type=config.provider_type,
                model_name=config.model_name,
                base_url=config.base_url,
                api_key_ref=config.api_key_ref,
                is_default=config.is_default,
                connected=connected,
                local=_provider_local(config.provider_type),
            )
        )
    return responses


@app.post(f"{settings.api_prefix}/settings/providers", response_model=ProviderConfigResponse, status_code=201)
async def create_provider_config(
    body: ProviderConfigRequest,
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
    secrets: Annotated[SecretStore, Depends(get_secrets)],
) -> ProviderConfigResponse:
    api_key_ref = secrets.put(body.api_key) if body.api_key else None
    config = registry.create_config(
        role=body.role,
        provider_type=body.provider_type,
        model_name=body.model_name,
        base_url=body.base_url,
        api_key_ref=api_key_ref,
        is_default=body.is_default,
    )
    try:
        connected = registry.test_connectivity(config.id).reachable
    except Exception:
        connected = False
    return ProviderConfigResponse(
        id=config.id,
        role=config.role,
        provider_type=config.provider_type,
        model_name=config.model_name,
        base_url=config.base_url,
        api_key_ref=config.api_key_ref,
        is_default=config.is_default,
        connected=connected,
        local=_provider_local(config.provider_type),
    )


@app.delete(f"{settings.api_prefix}/settings/providers/{{config_id}}", status_code=204)
async def delete_provider_config(
    config_id: str,
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
    secrets: Annotated[SecretStore, Depends(get_secrets)],
) -> Response:
    existing = registry.get_config(config_id)
    if existing is None:
        raise DuckDocsError("not_found", "Provider config was not found.", 404)
    if existing.api_key_ref:
        secrets.delete(existing.api_key_ref)
    registry.delete_config(config_id)
    return Response(status_code=204)


@app.post(f"{settings.api_prefix}/settings/providers/{{config_id}}/test", response_model=ProviderTestResponse)
async def test_provider_config(
    config_id: str,
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
) -> ProviderTestResponse:
    if registry.get_config(config_id) is None:
        raise DuckDocsError("not_found", "Provider config was not found.", 404)
    status = registry.test_connectivity(config_id)
    return ProviderTestResponse(reachable=status.reachable, latency_ms=status.latency_ms, error=status.error)


@app.get(f"{settings.api_prefix}/ingest-jobs/stream")
async def job_stream(repo: Annotated[AnyRepository, Depends(get_repository)]) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        for job in repo.jobs.values():
            yield f"event: job_update\ndata: {job.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
