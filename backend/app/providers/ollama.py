"""Thin Ollama HTTP adapters (docs/12_PROVIDER_ARCHITECTURE.md)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from app.providers.base import HealthStatus, ProviderRef


class OllamaChatAdapter:
    def __init__(self, *, base_url: str, model_name: str, config_id: str = "cfg_chat_ollama") -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.ref: ProviderRef = {
            "role": "chat",
            "provider_type": "ollama",
            "model_name": model_name,
            "base_url": self.base_url,
            "config_id": config_id,
        }

    def generate(self, prompt: str, *, stream: bool = True) -> Iterator[str] | str:
        payload = {"model": self.model_name, "prompt": prompt, "stream": stream}
        if stream:
            return self._stream(payload)
        body = self._post_json("/api/generate", payload)
        return str(body.get("response", ""))

    def _stream(self, payload: dict[str, Any]) -> Iterator[str]:
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                text = chunk.get("response")
                if text:
                    yield str(text)
                if chunk.get("done"):
                    break

    def health_check(self) -> HealthStatus:
        started = monotonic()
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models = {
                str(item.get("name", ""))
                for item in payload.get("models", [])
                if isinstance(item, dict)
            }
            if self.model_name and models:
                base = self.model_name.split(":")[0]
                matched = any(
                    name == self.model_name or name == base or name.startswith(f"{base}:") for name in models
                )
                if not matched:
                    return HealthStatus(
                        reachable=False,
                        latency_ms=round((monotonic() - started) * 1000, 2),
                        error=f"Model '{self.model_name}' is not installed in Ollama.",
                        checked_at=datetime.now(UTC),
                    )
            return HealthStatus(
                reachable=True,
                latency_ms=round((monotonic() - started) * 1000, 2),
                error=None,
                checked_at=datetime.now(UTC),
            )
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            return HealthStatus(
                reachable=False,
                latency_ms=None,
                error=str(error),
                checked_at=datetime.now(UTC),
            )

    @property
    def context_window(self) -> int:
        return 8192

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama {error.code} for model '{self.model_name}': {detail}") from error


class OllamaEmbeddingAdapter:
    def __init__(self, *, base_url: str, model_name: str, config_id: str = "cfg_embed_ollama") -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.ref: ProviderRef = {
            "role": "embedding",
            "provider_type": "ollama",
            "model_name": model_name,
            "base_url": self.base_url,
            "config_id": config_id,
        }
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            body = self._post_json("/api/embeddings", {"model": self.model_name, "prompt": text})
            vector = [float(value) for value in body.get("embedding", [])]
            if self._dimension is None and vector:
                self._dimension = len(vector)
            vectors.append(vector)
        return vectors

    def health_check(self) -> HealthStatus:
        return OllamaChatAdapter(base_url=self.base_url, model_name=self.model_name).health_check()

    @property
    def dimension(self) -> int:
        return self._dimension or 768

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama {error.code} for model '{self.model_name}': {detail}") from error
