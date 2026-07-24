"""Provider adapter contracts from docs/12_PROVIDER_ARCHITECTURE.md."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, TypedDict


class ProviderRef(TypedDict):
    role: Literal["chat", "embedding"]
    provider_type: Literal["ollama", "openai", "anthropic", "gemini", "openai_compatible", "extractive", "keyword"]
    model_name: str
    base_url: str | None
    config_id: str


@dataclass(slots=True)
class HealthStatus:
    reachable: bool
    latency_ms: float | None
    error: str | None
    checked_at: datetime


class ChatProviderAdapter(Protocol):
    ref: ProviderRef

    def generate(self, prompt: str, *, stream: bool = True) -> Iterator[str] | str: ...

    def health_check(self) -> HealthStatus: ...

    @property
    def context_window(self) -> int: ...


class EmbeddingProviderAdapter(Protocol):
    ref: ProviderRef

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def health_check(self) -> HealthStatus: ...

    @property
    def dimension(self) -> int: ...
