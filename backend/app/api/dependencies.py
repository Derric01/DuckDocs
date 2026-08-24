"""Shared singletons and FastAPI dependencies.

Kept in one module so routers depend on the seam rather than on `main`,
which would otherwise make every router import the app and create cycles.
Tests override these with `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Request

from app.core.config import Settings, settings
from app.providers.registry import ProviderRegistry
from app.providers.secrets import SecretStore
from app.repositories import AnyRepository
from app.repositories.sql import build_repository
from app.services.rag import RagService
from app.services.vector_store import VectorStore

repository: AnyRepository = build_repository(settings.data_root, settings.db_url)
provider_registry = ProviderRegistry(settings)
secret_store = SecretStore(settings.data_root)
vector_store = VectorStore(settings)


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


RepositoryDep = Annotated[AnyRepository, Depends(get_repository)]
SettingsDep = Annotated[Settings, Depends(get_runtime_settings)]
RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
SecretsDep = Annotated[SecretStore, Depends(get_secrets)]
RagDep = Annotated[RagService, Depends(get_rag)]
