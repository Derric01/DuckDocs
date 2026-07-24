"""Typed API errors and the stable error envelope from docs/33_ERROR_HANDLING.md."""

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class DuckDocsError(Exception):
    code: str
    message: str
    status_code: int = 400
    suggested_action: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None
    correlation_id: str | None = None


async def duckdocs_error_handler(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, DuckDocsError):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The API encountered an unexpected error.",
                    "retryable": False,
                    "details": {},
                }
            },
        )
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "suggested_action": error.suggested_action,
                "retryable": error.retryable,
                "correlation_id": error.correlation_id,
                "details": error.details or {},
            }
        },
    )
