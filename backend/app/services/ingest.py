"""Ingestion orchestration.

The pipeline is: parse (with OCR fallback) -> chunk -> summarize -> embed ->
index. Each stage reports progress to the job so the Library can show what
is actually happening rather than a bare spinner.

Durability
----------
Ingestion runs in-process. If the API exits mid-run, the work is lost but the
job row still says `processing`, which would leave a document stuck on that
status forever with no way to tell a live run from a dead one.

`reconcile_orphaned_jobs` closes that hole at startup: any job still marked
running when the process starts cannot belong to this process, so it is
failed with an actionable reason instead of hanging. Retry then re-runs it
from the stored file. This is deliberately simpler than a broker — it keeps
the single-binary deployment while removing the silent-corruption case.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.core.config import Settings
from app.domain.models import IngestJob
from app.repositories import AnyRepository
from app.services.chunking import AnchorQuality, chunk_document
from app.services.parsing import ParsedDocument, parse_upload
from app.services.rag import RagService
from app.services.summarize import (
    DocumentSummary,
    build_summary_prompt,
    clean_model_summary,
    summarize_extractive,
)

logger = logging.getLogger("duckdocs.ingest")

RUNNING_STATES = {"queued", "processing"}


def anchor_quality_for(suffix: str, parsed: ParsedDocument) -> AnchorQuality:
    if suffix == "xlsx":
        return "cell"
    if parsed.fidelity_tier == "structural":
        return "line"
    return "paragraph"


def reconcile_orphaned_jobs(repo: AnyRepository) -> list[IngestJob]:
    """Fail jobs left running by a previous process.

    Called once at startup. Nothing else can legitimately be mid-run at that
    moment, so anything still `queued`/`processing` was orphaned by an exit.
    """
    orphaned: list[IngestJob] = []
    for job in list(repo.jobs.values()):
        if job.status not in RUNNING_STATES:
            continue
        updated = repo.update_job(
            job.id,
            status="failed",
            stage="failed",
            error={
                "stage": job.stage,
                "reason_code": "interrupted",
                "human_message": (
                    "Processing stopped when the API restarted. The file is still stored — retry to process it again."
                ),
            },
        )
        # The document must not keep claiming it is being worked on.
        repo.update_document(job.document_id, status="review")
        if updated is not None:
            orphaned.append(updated)

    if orphaned:
        logger.warning("Failed %d ingest job(s) orphaned by a previous run", len(orphaned))
    return orphaned


async def build_document_summary(
    parsed: ParsedDocument,
    document_id: str,
    repo: AnyRepository,
    rag: RagService,
    runtime: Settings,
) -> DocumentSummary:
    """Summarize a freshly parsed document.

    The extractive summary is computed first and kept as the floor: it is
    verbatim document text, so it is always safe to show. A chat provider is
    then given a chance to write something more readable. If none is
    connected, or it errors, the extractive result stands -- summarization
    must never fail an ingest.
    """
    baseline = await asyncio.to_thread(summarize_extractive, parsed)

    if not runtime.summarize_with_model:
        return baseline

    chat = rag.registry.get_chat_provider()
    # The built-in extractive adapter expects RAG chunk markers, not prose,
    # so asking it to summarize would produce a refusal token.
    if chat.ref["provider_type"] in {"extractive", "keyword"}:
        return baseline

    document = repo.get_document(document_id)
    prompt = build_summary_prompt(document.name if document else "Untitled", parsed)
    try:
        raw = await asyncio.to_thread(chat.generate, prompt, stream=False)
    except Exception:
        logger.info("Model summary failed for %s; keeping the extractive summary", document_id)
        return baseline

    text = clean_model_summary(raw if isinstance(raw, str) else "".join(raw))
    if len(text) < 24:
        return baseline
    return DocumentSummary(
        text=text,
        method="abstractive",
        provider=f"{chat.ref['provider_type']}:{chat.ref['model_name']}",
    )


async def process_ingest(
    repo: AnyRepository,
    rag: RagService,
    runtime: Settings,
    document_id: str,
    job_id: str,
    payload: bytes,
    suffix: str,
) -> None:
    """Run the pipeline for one uploaded document.

    Parsing/OCR is CPU-bound and can take a while on a large scanned PDF, so
    it runs in a worker thread rather than inline on the event loop -- the API
    stays responsive to health checks and other requests throughout.
    """
    try:
        await _run_pipeline(repo, rag, runtime, document_id, job_id, payload, suffix)
    except Exception:
        # An unexpected failure must still leave honest state behind rather
        # than a job frozen at whatever stage it reached.
        logger.exception("Ingest failed for document %s", document_id)
        repo.update_job(
            job_id,
            status="failed",
            stage="failed",
            progress_pct=100,
            error={
                "stage": "unknown",
                "reason_code": "internal_error",
                "human_message": "Processing failed unexpectedly. Retry, or check the API logs.",
            },
        )
        repo.update_document(document_id, status="review")


async def _run_pipeline(
    repo: AnyRepository,
    rag: RagService,
    runtime: Settings,
    document_id: str,
    job_id: str,
    payload: bytes,
    suffix: str,
) -> None:
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

    repo.update_job(job_id, status="processing", stage="chunking", progress_pct=62)
    anchor_quality = anchor_quality_for(suffix, parsed)
    chunks = await asyncio.to_thread(chunk_document, parsed, runtime, anchor_quality)

    repo.update_job(job_id, status="processing", stage="summarizing", progress_pct=72)
    summary = await build_document_summary(parsed, document_id, repo, rag, runtime)

    repo.update_job(job_id, status="processing", stage="embedding", progress_pct=82)
    indexed_count = repo.index_document_chunks(document_id, chunks, parsed.ocr_engine)

    if indexed_count:
        repo.update_job(job_id, status="processing", stage="indexing", progress_pct=92)
        await asyncio.to_thread(rag.index_document, document_id)

    # Keep the larger of the probed and parsed counts: a parser may skip pages
    # it found nothing on, but those pages exist and are still previewable.
    existing = repo.get_document(document_id)
    page_count = max(parsed.page_count, existing.pages if existing else 1)

    repo.update_document(
        document_id,
        status="ready" if indexed_count else "review",
        fidelity_tier=parsed.fidelity_tier,
        pages=page_count,
        summary=summary.text or None,
        summary_method=summary.method,
        summary_provider=summary.provider,
    )
    repo.update_job(job_id, status="ready", stage="ready", progress_pct=100)


def stored_file_path(runtime: Settings, document_id: str, name: str) -> Path:
    return runtime.data_root / "documents" / document_id / name
