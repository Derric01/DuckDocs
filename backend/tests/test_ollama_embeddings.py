from __future__ import annotations

from app.providers.ollama import OllamaEmbeddingAdapter


def test_embedding_adapter_sends_batch_to_current_ollama_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    adapter = OllamaEmbeddingAdapter(base_url="http://ollama:11434", model_name="nomic-embed-text")
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_post(path: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((path, payload))
        return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    monkeypatch.setattr(adapter, "_post_json", fake_post)

    vectors = adapter.embed(["climate text", "question text"])

    assert calls == [
        (
            "/api/embed",
            {"model": "nomic-embed-text", "input": ["climate text", "question text"]},
        )
    ]
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert adapter.dimension == 2
