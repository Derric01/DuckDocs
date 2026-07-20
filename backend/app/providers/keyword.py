"""Keyword embedding stub used when no embedding provider is connected."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from app.providers.base import HealthStatus, ProviderRef


class KeywordEmbeddingAdapter:
    """Deterministic bag-of-words hash vectors for offline indexing/search fallback."""

    def __init__(self, dimension: int = 64, config_id: str = "cfg_embed_keyword") -> None:
        self._dimension = dimension
        self.ref: ProviderRef = {
            "role": "embedding",
            "provider_type": "keyword",
            "model_name": "local_text_match",
            "base_url": None,
            "config_id": config_id,
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def health_check(self) -> HealthStatus:
        return HealthStatus(reachable=True, latency_ms=0.0, error=None, checked_at=datetime.now(UTC))

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in text.lower().split():
            digest = sha256(token.encode("utf-8")).digest()
            index = digest[0] % self._dimension
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        if norm:
            return [value / norm for value in vector]
        return vector
