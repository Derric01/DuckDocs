"""Retrieval, grounded answers, and evidence lookup."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.dependencies import RagDep, RegistryDep, RepositoryDep
from app.core.errors import DuckDocsError
from app.domain.models import AskRequest, GroundedResponse, SearchRequest, SearchResponse, SearchResult

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, rag: RagDep, registry: RegistryDep) -> SearchResponse:
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


@router.post("/ask", response_model=GroundedResponse)
async def ask(request: AskRequest, rag: RagDep) -> GroundedResponse:
    return rag.ask(request.query, request.scope)


@router.post("/ask/stream")
async def ask_stream(request: AskRequest, rag: RagDep) -> StreamingResponse:
    """Server-sent events: tokens as they are produced, then the full result.

    The terminal `done` event carries the complete GroundedResponse, so the
    client gets citations, provider, and refusal state without a second call
    -- and a client that misses tokens can still render from `done` alone.
    """
    result, tokens = await asyncio.to_thread(rag.ask_stream_tokens, request.query, request.scope)

    async def events() -> AsyncIterator[str]:
        for index, token in enumerate(tokens):
            yield f"event: token\ndata: {json.dumps({'index': index, 'text': token})}\n\n"
            # Yield to the loop so tokens actually flush rather than arriving
            # as one buffered chunk.
            await asyncio.sleep(0.012)
        yield f"event: done\ndata: {result.model_dump_json()}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str, repo: RepositoryDep) -> object:
    item = repo.evidence.get(evidence_id)
    if item is None:
        raise DuckDocsError("not_found", "Evidence was not found.", 404)
    return item
