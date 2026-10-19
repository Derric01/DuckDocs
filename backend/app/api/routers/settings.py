"""Provider configuration and workspace settings."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Response

from app.api.dependencies import RegistryDep, SecretsDep
from app.core.errors import DuckDocsError
from app.domain.models import (
    Provider,
    ProviderConfigRequest,
    ProviderConfigResponse,
    ProviderTestResponse,
    SettingsResponse,
)

router = APIRouter(tags=["settings"])


def _is_local_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        return False
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".docker.internal"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Compose service names are single-label DNS names on the private
        # application network (for example, "ollama").
        return "." not in host and host not in {"metadata", "metadata.google.internal"}


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


@router.get("/providers", response_model=list[Provider])
async def providers(registry: RegistryDep) -> list[Provider]:
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


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint(registry: RegistryDep) -> SettingsResponse:
    return SettingsResponse(local_only=registry.settings.strict_local, providers=await providers(registry))


@router.get("/settings/providers", response_model=list[ProviderConfigResponse])
async def list_provider_configs(registry: RegistryDep) -> list[ProviderConfigResponse]:
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


@router.post("/settings/providers", response_model=ProviderConfigResponse, status_code=201)
async def create_provider_config(
    body: ProviderConfigRequest,
    registry: RegistryDep,
    secrets: SecretsDep,
) -> ProviderConfigResponse:
    if registry.settings.strict_local:
        if body.provider_type in {"openai", "anthropic", "gemini"}:
            raise DuckDocsError("strict_local", "Remote providers are disabled while strict local mode is on.", 400)
        if body.base_url and not _is_local_url(body.base_url):
            raise DuckDocsError("strict_local", "Provider URL must point to localhost or a Docker-internal host.", 400)
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


@router.delete("/settings/providers/{config_id}", status_code=204)
async def delete_provider_config(
    config_id: str,
    registry: RegistryDep,
    secrets: SecretsDep,
) -> Response:
    existing = registry.get_config(config_id)
    if existing is None:
        raise DuckDocsError("not_found", "Provider config was not found.", 404)
    if existing.api_key_ref:
        secrets.delete(existing.api_key_ref)
    registry.delete_config(config_id)
    return Response(status_code=204)


@router.post("/settings/providers/{config_id}/test", response_model=ProviderTestResponse)
async def test_provider_config(
    config_id: str,
    registry: RegistryDep,
) -> ProviderTestResponse:
    if registry.get_config(config_id) is None:
        raise DuckDocsError("not_found", "Provider config was not found.", 404)
    status = registry.test_connectivity(config_id)
    return ProviderTestResponse(reachable=status.reachable, latency_ms=status.latency_ms, error=status.error)
