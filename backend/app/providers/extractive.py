"""Offline extractive chat fallback — synthesizes answers from retrieved evidence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from app.providers.base import HealthStatus, ProviderRef


class ExtractiveChatAdapter:
    """Deterministic local synthesizer used when no LLM provider is connected."""

    def __init__(self, config_id: str = "cfg_chat_extractive") -> None:
        self.ref: ProviderRef = {
            "role": "chat",
            "provider_type": "extractive",
            "model_name": "evidence_synthesis_v1",
            "base_url": None,
            "config_id": config_id,
        }

    def generate(self, prompt: str, *, stream: bool = True) -> Iterator[str] | str:
        # The RAG layer passes a prompt that already includes chunk markers.
        # Extractive mode emits a short grounded summary citing included chunks,
        # or INSUFFICIENT_EVIDENCE when no chunk markers are present.
        chunk_ids = _extract_chunk_ids(prompt)
        if not chunk_ids:
            text = "INSUFFICIENT_EVIDENCE"
        else:
            snippets = _extract_chunk_bodies(prompt)
            pairs = list(zip(chunk_ids, snippets, strict=False))[:3]
            cited_parts: list[str] = []
            for chunk_id, snippet in pairs:
                cleaned = snippet.strip().rstrip(".!?")
                cited_parts.append(f"{cleaned} [chunk:{chunk_id}].")
            cited = " ".join(cited_parts)
            text = f"Based on the retrieved evidence, {cited}".strip()
        if stream:
            return iter([text])
        return text

    def health_check(self) -> HealthStatus:
        return HealthStatus(reachable=True, latency_ms=0.0, error=None, checked_at=datetime.now(UTC))

    @property
    def context_window(self) -> int:
        return 8192


def _extract_chunk_ids(prompt: str) -> list[str]:
    import re

    return re.findall(r"\[\[chunk:([^\]]+)\]\]", prompt)


def _extract_chunk_bodies(prompt: str) -> list[str]:
    import re

    return [match.strip()[:240] for match in re.findall(r"\[\[chunk:[^\]]+\]\](.*?)\[\[/chunk\]\]", prompt, flags=re.S)]
