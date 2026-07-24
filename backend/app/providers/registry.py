"""Provider registry with offline-safe resolution (docs/12)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.core.config import Settings
from app.providers.base import ChatProviderAdapter, EmbeddingProviderAdapter, HealthStatus
from app.providers.extractive import ExtractiveChatAdapter
from app.providers.keyword import KeywordEmbeddingAdapter
from app.providers.ollama import OllamaChatAdapter, OllamaEmbeddingAdapter

ProviderRole = Literal["chat", "embedding"]
ProviderType = Literal["ollama", "openai", "anthropic", "gemini", "openai_compatible", "extractive", "keyword"]


@dataclass(slots=True)
class ProviderConfig:
    id: str
    role: ProviderRole
    provider_type: ProviderType
    model_name: str
    base_url: str | None = None
    api_key_ref: str | None = None
    is_default: bool = False


class ProviderRegistry:
    def __init__(self, settings: Settings, config_path: Path | None = None) -> None:
        self.settings = settings
        self.config_path = config_path or (settings.data_root / "provider_configs.json")
        self._configs: list[ProviderConfig] = []
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            self._configs = self._default_configs()
            self._persist()
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._configs = self._default_configs()
            return
        configs: list[ProviderConfig] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                try:
                    configs.append(
                        ProviderConfig(
                            id=str(item["id"]),
                            role=item["role"],
                            provider_type=item["provider_type"],
                            model_name=str(item.get("model_name", "")),
                            base_url=item.get("base_url"),
                            api_key_ref=item.get("api_key_ref"),
                            is_default=bool(item.get("is_default", False)),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
        self._configs = configs or self._default_configs()

    def _default_configs(self) -> list[ProviderConfig]:
        return [
            ProviderConfig(
                id="cfg_chat_ollama",
                role="chat",
                provider_type="ollama",
                model_name=self.settings.chat_model,
                base_url=self.settings.ollama_base_url,
                is_default=True,
            ),
            ProviderConfig(
                id="cfg_embed_ollama",
                role="embedding",
                provider_type="ollama",
                model_name=self.settings.embed_model,
                base_url=self.settings.ollama_base_url,
                is_default=True,
            ),
            ProviderConfig(
                id="cfg_chat_extractive",
                role="chat",
                provider_type="extractive",
                model_name="evidence_synthesis_v1",
                is_default=False,
            ),
            ProviderConfig(
                id="cfg_embed_keyword",
                role="embedding",
                provider_type="keyword",
                model_name="local_text_match",
                is_default=False,
            ),
        ]

    def _persist(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": config.id,
                "role": config.role,
                "provider_type": config.provider_type,
                "model_name": config.model_name,
                "base_url": config.base_url,
                "api_key_ref": config.api_key_ref,
                "is_default": config.is_default,
            }
            for config in self._configs
        ]
        self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def list_configs(self) -> list[ProviderConfig]:
        return list(self._configs)

    def get_config(self, config_id: str) -> ProviderConfig | None:
        return next((config for config in self._configs if config.id == config_id), None)

    def upsert_config(self, config: ProviderConfig) -> ProviderConfig:
        if config.is_default:
            for existing in self._configs:
                if existing.role == config.role:
                    existing.is_default = False
        replaced = False
        for index, existing in enumerate(self._configs):
            if existing.id == config.id:
                self._configs[index] = config
                replaced = True
                break
        if not replaced:
            self._configs.append(config)
        self._persist()
        return config

    def delete_config(self, config_id: str) -> bool:
        before = len(self._configs)
        self._configs = [config for config in self._configs if config.id != config_id]
        if len(self._configs) == before:
            return False
        self._persist()
        return True

    def create_config(
        self,
        *,
        role: ProviderRole,
        provider_type: ProviderType,
        model_name: str,
        base_url: str | None = None,
        api_key_ref: str | None = None,
        is_default: bool = False,
    ) -> ProviderConfig:
        config = ProviderConfig(
            id=f"cfg_{uuid4().hex[:12]}",
            role=role,
            provider_type=provider_type,
            model_name=model_name,
            base_url=base_url,
            api_key_ref=api_key_ref,
            is_default=is_default,
        )
        return self.upsert_config(config)

    def _default_for(self, role: ProviderRole) -> ProviderConfig | None:
        return next((config for config in self._configs if config.role == role and config.is_default), None)

    def resolve(self, config_id: str) -> ChatProviderAdapter | EmbeddingProviderAdapter:
        config = self.get_config(config_id)
        if config is None:
            raise KeyError(config_id)
        return self._build(config)

    def get_chat_provider(self) -> ChatProviderAdapter:
        preferred = self._default_for("chat")
        if preferred is not None:
            adapter = self._build(preferred)
            if preferred.provider_type == "extractive":
                return adapter  # type: ignore[return-value]
            health = adapter.health_check()
            if health.reachable:
                return adapter  # type: ignore[return-value]
        return ExtractiveChatAdapter()

    def get_embedding_provider(self) -> EmbeddingProviderAdapter:
        preferred = self._default_for("embedding")
        if preferred is not None:
            adapter = self._build(preferred)
            if preferred.provider_type == "keyword":
                return adapter  # type: ignore[return-value]
            health = adapter.health_check()
            if health.reachable:
                return adapter  # type: ignore[return-value]
        return KeywordEmbeddingAdapter()

    def test_connectivity(self, config_id: str) -> HealthStatus:
        adapter = self.resolve(config_id)
        return adapter.health_check()

    def _build(self, config: ProviderConfig) -> ChatProviderAdapter | EmbeddingProviderAdapter:
        if config.role == "chat":
            if config.provider_type == "ollama":
                return OllamaChatAdapter(
                    base_url=config.base_url or self.settings.ollama_base_url,
                    model_name=config.model_name or self.settings.chat_model,
                    config_id=config.id,
                )
            if config.provider_type == "extractive":
                return ExtractiveChatAdapter(config_id=config.id)
            # Cloud types are registered but not auto-called without explicit use.
            return ExtractiveChatAdapter(config_id=config.id)
        if config.provider_type == "ollama":
            return OllamaEmbeddingAdapter(
                base_url=config.base_url or self.settings.ollama_base_url,
                model_name=config.model_name or self.settings.embed_model,
                config_id=config.id,
            )
        return KeywordEmbeddingAdapter(config_id=config.id)

    def status_snapshot(self) -> dict[str, Any]:
        chat = self.get_chat_provider()
        embed = self.get_embedding_provider()
        return {
            "chat": {
                "provider_type": chat.ref["provider_type"],
                "model": chat.ref["model_name"],
                "local": chat.ref["provider_type"] in {"ollama", "extractive"},
                "connected": chat.health_check().reachable,
            },
            "embedding": {
                "provider_type": embed.ref["provider_type"],
                "model": embed.ref["model_name"],
                "local": embed.ref["provider_type"] in {"ollama", "keyword"},
                "connected": embed.health_check().reachable,
            },
        }
