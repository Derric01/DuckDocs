from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.domain.models import Evidence
from app.providers.ollama import OllamaChatAdapter
from app.repositories.memory import DocumentRepository
from app.services.rag import GroundingGate, RagService, build_ask_prompt
from app.services.vector_store import RetrievedChunk, VectorStore


def _gate_result(output: str, evidence: str = "The marker is ALPHA.") -> str:
    return GroundingGate().validate(
        output,
        {"ev_alpha"},
        task="ask",
        evidence_by_id={"ev_alpha": evidence},
        query="What is the marker?",
    ).outcome


def test_gate_rejects_prompt_template_echo() -> None:
    assert _gate_result("Question: What is the marker?\nAnswer: ALPHA. [chunk:ev_alpha]") == "insufficient_evidence"


def test_gate_rejects_question_echo() -> None:
    assert _gate_result("What is the marker? [chunk:ev_alpha]") == "insufficient_evidence"


def test_gate_rejects_persona_echo() -> None:
    assert _gate_result("I am DuckDocs Waymark. [chunk:ev_alpha]", "DuckDocs Waymark is a local guide.") == (
        "insufficient_evidence"
    )


def test_gate_rejects_prompt_example_echo() -> None:
    assert _gate_result(
        "The record identifies the Engineering department. [chunk:ev_alpha]",
        "The record identifies the Engineering department.",
    ) == "insufficient_evidence"


def test_gate_rejects_first_person_or_meta_sentence() -> None:
    assert _gate_result("I found the answer in the evidence. [chunk:ev_alpha]", "I found the answer in the evidence.") == (
        "insufficient_evidence"
    )


def test_ask_prompt_has_no_persona_or_example_answer() -> None:
    evidence = Evidence(
        id="ev_alpha",
        document_id="doc_alpha",
        document_name="alpha.txt",
        section="Imported content",
        page=1,
        line_start=1,
        line_end=1,
        snippet="The marker is ALPHA.",
        retrieval_score=0.9,
        relevance="High",
    )
    prompt = build_ask_prompt("What is the marker?", [])
    assert "Waymark" not in prompt
    assert "Engineering department" not in prompt
    assert evidence.snippet not in prompt


def test_ask_prompt_caps_context_size() -> None:
    chunks = [
        RetrievedChunk(
            evidence=Evidence(
                id=f"ev_{index}",
                document_id="doc",
                document_name="file.txt",
                section="section",
                page=1,
                line_start=1,
                line_end=1,
                snippet="x" * 500,
                retrieval_score=0.9,
                relevance="High",
            ),
            score=0.9,
        )
        for index in range(8)
    ]
    prompt = build_ask_prompt("What is the marker?", chunks, max_chunks=6, max_chars=100)
    assert prompt.count("[[chunk:") == 6
    assert "x" * 101 not in prompt


def test_ollama_ask_payload_is_deterministic(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    adapter = OllamaChatAdapter(base_url="http://ollama:11434", model_name="llama3.2:1b")
    calls: list[dict[str, object]] = []

    def fake_post(path: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        return {"response": "ok"}

    monkeypatch.setattr(adapter, "_post_json", fake_post)
    adapter.generate("prompt", stream=False, structured_output=True)
    assert calls[0]["options"] == {
        "temperature": 0,
        "seed": 0,
        "num_predict": 128,
        "num_ctx": 4096,
    }
    assert calls[0]["format"] == "json"


def test_gate_accepts_only_verified_structured_claims() -> None:
    result = GroundingGate().validate(
        '{"claims":[{"claim":"The marker is ALPHA.","evidence_id":"ev_alpha","quote":"The marker is ALPHA."},'
        '{"claim":"The marker is BETA.","evidence_id":"ev_alpha","quote":"The marker is BETA."}]}',
        {"ev_alpha"},
        task="ask",
        evidence_by_id={"ev_alpha": "The marker is ALPHA."},
        query="What is the marker?",
    )
    assert result.outcome == "grounded"
    assert result.cited_ids == ["ev_alpha"]
    assert result.text == "The marker is ALPHA [chunk:ev_alpha]."


def test_gate_accepts_simple_answer_with_verified_passage_number() -> None:
    result = GroundingGate().validate(
        '{"answer":"The marker is ALPHA.","evidence_ids":["1"]}',
        {"1"},
        task="ask",
        evidence_by_id={"1": "The marker is ALPHA."},
        query="What is the marker?",
    )
    assert result.outcome == "grounded"
    assert result.cited_ids == ["1"]


def test_gate_rejects_simple_answer_with_empty_passage() -> None:
    result = GroundingGate().validate(
        '{"answer":"The marker is ALPHA.","evidence_ids":["1"]}',
        {"1"},
        task="ask",
        evidence_by_id={"1": ""},
        query="What is the marker?",
    )
    assert result.outcome == "insufficient_evidence"


def test_empty_selected_passages_are_not_returned_as_citations() -> None:
    evidence = Evidence(
        id="ev_alpha",
        document_id="doc_alpha",
        document_name="alpha.txt",
        section="Imported content",
        page=1,
        line_start=1,
        line_end=1,
        snippet="The marker is ALPHA.",
        retrieval_score=0.9,
        relevance="High",
    )
    repo = DocumentRepository(Path("test-phase2-data"))
    repo.evidence = {evidence.id: evidence}
    settings = Settings(data_root=Path("test-phase2-data"))
    registry = type("Registry", (), {})()
    vector_store = VectorStore(settings)
    service = RagService(settings, repo, registry, vector_store)
    citations = service._bind_citations(["ev_alpha"], [], "unrelated question", "ALPHA [chunk:ev_alpha]")
    assert citations == []


def test_failed_primary_provider_fallback_reports_actual_provider() -> None:
    evidence = Evidence(
        id="ev_alpha",
        document_id="doc_alpha",
        document_name="alpha.txt",
        section="Imported content",
        page=1,
        line_start=1,
        line_end=1,
        snippet="The marker is ALPHA.",
        retrieval_score=0.9,
        relevance="High",
    )
    repo = DocumentRepository(Path("test-phase2-data"))
    repo.evidence = {evidence.id: evidence}

    class InvalidChat:
        ref = {
            "role": "chat",
            "provider_type": "ollama",
            "model_name": "test",
            "base_url": "http://ollama:11434",
            "config_id": "invalid",
        }

        def generate(self, prompt: str, *, stream: bool = False, structured_output: bool = False) -> str:
            return "I am DuckDocs Waymark. [chunk:ev_alpha]"

    class Registry:
        chat = InvalidChat()

        def get_chat_provider(self):
            return self.chat

        def get_embedding_provider(self):
            from app.providers.keyword import KeywordEmbeddingAdapter

            return KeywordEmbeddingAdapter()

    service = RagService(Settings(data_root=Path("test-phase2-data")), repo, Registry(), VectorStore(Settings()))
    service.retrieve = lambda query, scope=None: [service._keyword_chunk(query, evidence)]  # type: ignore[method-assign]
    response = service.ask("What is the marker ALPHA?")
    assert response.outcome == "grounded", (
        response.outcome,
        response.refusal_reason,
        response.retrieved_chunk_count,
        response.provider,
    )
    assert response.provider["name"] == "extractive"
    assert response.citations
    assert all(citation.snippet for citation in response.citations)
