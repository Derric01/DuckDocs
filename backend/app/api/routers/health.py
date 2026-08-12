"""Liveness and readiness (docs/31_OBSERVABILITY.md)."""

from __future__ import annotations

from time import monotonic

from fastapi import APIRouter

from app.api.dependencies import RegistryDep, SettingsDep, VectorStoreDep
from app.services.ocr import build_engine

router = APIRouter(tags=["health"])
_started_at = monotonic()


@router.get("/health")
async def health(runtime: SettingsDep) -> dict[str, object]:
    return {"status": "ok", "version": runtime.version, "uptime_s": round(monotonic() - _started_at, 2)}


@router.get("/ready")
async def ready(registry: RegistryDep, store: VectorStoreDep, runtime: SettingsDep) -> dict[str, object]:
    snapshot = registry.status_snapshot()
    ocr_engine = build_engine(runtime)
    return {
        "status": "ready",
        "checks": {
            "metadata_store": "postgres" if runtime.db_url else "json",
            "file_store": "ok",
            "vector_store": store.health(),
            "ocr_engine": ocr_engine.name,
            "ocr_ready": ocr_engine.available(),
            "ollama": "ok"
            if snapshot["chat"]["provider_type"] == "ollama" and snapshot["chat"]["connected"]
            else "optional",
            "chat_provider": f"{snapshot['chat']['provider_type']}:{snapshot['chat']['model']}",
            "embedding_provider": f"{snapshot['embedding']['provider_type']}:{snapshot['embedding']['model']}",
        },
    }
