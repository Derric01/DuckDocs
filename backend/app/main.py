"""FastAPI application for DuckDocs.

Composition only: middleware, router wiring, and lifespan. Route handlers
live in `app/api/routers`, shared singletons in `app/api/dependencies`.

Implements the P0 API seam in docs/15_API_SPECIFICATION.md, the local health
contract in docs/31_OBSERVABILITY.md, and the honest refusal path in
docs/33_ERROR_HANDLING.md.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.dependencies import repository
from app.api.routers import documents, health, search
from app.api.routers import settings as settings_router
from app.core.config import settings
from app.core.errors import DuckDocsError, duckdocs_error_handler
from app.services.ingest import reconcile_orphaned_jobs
from app.services.preview import clear_preview_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("duckdocs")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_root.mkdir(parents=True, exist_ok=True)
    (settings.data_root / "documents").mkdir(parents=True, exist_ok=True)

    # Ingestion runs in-process, so a job still marked running at startup was
    # orphaned by a previous exit and will never progress on its own. Fail it
    # with an actionable reason rather than leaving it stuck forever.
    orphaned = reconcile_orphaned_jobs(repository)
    if orphaned:
        logger.warning("Recovered %d interrupted ingest job(s); they can be retried", len(orphaned))

    yield

    clear_preview_cache()


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


@app.middleware("http")
async def local_auth_and_correlation(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Enforce optional local bearer auth and propagate a correlation id."""
    request_id = request.headers.get("X-Correlation-Id", f"req_{uuid4().hex[:16]}")
    if settings.api_token and request.url.path.startswith(settings.api_prefix):
        if request.headers.get("Authorization") != f"Bearer {settings.api_token}":
            unauthorized = JSONResponse(
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
            unauthorized.headers["X-Correlation-Id"] = request_id
            return unauthorized
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = request_id
    return response


app.include_router(health.router)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(settings_router.router, prefix=settings.api_prefix)
