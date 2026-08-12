import io
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_registry, get_repository, get_runtime_settings, get_vector_store
from app.core.config import Settings
from app.main import app
from app.providers.extractive import ExtractiveChatAdapter
from app.providers.registry import ProviderConfig, ProviderRegistry
from app.repositories.memory import DocumentRepository
from app.services.rag import GroundingGate
from app.services.vector_store import VectorStore


def client_with_data_root(data_root: Path) -> TestClient:
    repo = DocumentRepository(data_root)
    runtime = Settings(
        data_root=data_root,
        ollama_base_url="http://127.0.0.1:9",
        chroma_url=None,
        db_url=None,
    )
    registry = ProviderRegistry(runtime, config_path=data_root / "provider_configs.json")
    # Force offline-safe defaults for unit tests (no network).
    registry.upsert_config(
        ProviderConfig(
            id="cfg_chat_extractive",
            role="chat",
            provider_type="extractive",
            model_name="evidence_synthesis_v1",
            is_default=True,
        )
    )
    registry.upsert_config(
        ProviderConfig(
            id="cfg_embed_keyword",
            role="embedding",
            provider_type="keyword",
            model_name="local_text_match",
            is_default=True,
        )
    )
    store = VectorStore(runtime)
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_runtime_settings] = lambda: runtime
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_vector_store] = lambda: store
    return TestClient(app)


def make_docx(text: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_health_is_local_and_immediate() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_grounding_gate_refuses_when_library_is_empty(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        response = client.post("/api/v1/ask", json={"query": "What is the retention window?"})
        body = response.json()
        assert response.status_code == 200
        assert body["grounded"] is False
        assert body["outcome"] == "insufficient_evidence"
        assert body["citations"] == []
    app.dependency_overrides.clear()


def test_text_upload_becomes_searchable_evidence(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={
                "files": (
                    "local-retention-note.md",
                    b"DuckDocs local retention note\n\nFalcon records must stay on the local machine for 18 months.",
                    "text/markdown",
                )
            },
        )
        assert upload.status_code == 201

        search = client.post("/api/v1/search", json={"query": "falcon records 18 months"})
        body = search.json()
        assert search.status_code == 200
        assert body["results"]
        assert "Falcon records" in body["results"][0]["snippet"]

        answer = client.post("/api/v1/ask", json={"query": "How long do Falcon records stay local?"})
        answer_body = answer.json()
        assert answer.status_code == 200
        assert answer_body["grounded"] is True
        assert answer_body["citations"]

    app.dependency_overrides.clear()


def test_docx_upload_becomes_searchable_evidence(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={
                "files": (
                    "operating-note.docx",
                    make_docx("Northstar renewal evidence is reviewed every 45 days by operations."),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert upload.status_code == 201

        search = client.post("/api/v1/search", json={"query": "northstar renewal evidence"})
        body = search.json()
        assert search.status_code == 200
        assert body["results"]
        assert "Northstar renewal evidence" in body["results"][0]["snippet"]

    app.dependency_overrides.clear()


def test_grounding_gate_rejects_unknown_chunk_ids() -> None:
    gate = GroundingGate()
    result = gate.validate("The lease was signed [chunk:ev_missing].", allowed_chunk_ids={"ev_real"}, task="ask")
    assert result.outcome == "insufficient_evidence"
    assert result.reason == "gate_rejected_output"


def test_grounding_gate_respects_refusal_token() -> None:
    gate = GroundingGate()
    result = gate.validate("INSUFFICIENT_EVIDENCE", allowed_chunk_ids={"ev_real"}, task="ask")
    assert result.outcome == "insufficient_evidence"
    assert result.reason == "model_declined"


def test_grounding_gate_accepts_cited_answer() -> None:
    gate = GroundingGate()
    result = gate.validate(
        "Falcon records stay local for 18 months [chunk:ev_real].",
        allowed_chunk_ids={"ev_real"},
        task="ask",
    )
    assert result.outcome == "grounded"
    assert result.cited_ids == ["ev_real"]


def test_extractive_adapter_emits_citations_or_refusal() -> None:
    adapter = ExtractiveChatAdapter()
    refusal = adapter.generate("Question without chunks", stream=False)
    assert refusal == "INSUFFICIENT_EVIDENCE"
    answer = adapter.generate(
        "[[chunk:ev_01]]\nFalcon records stay local for 18 months.\n[[/chunk]]\nQuestion: how long?",
        stream=False,
    )
    assert isinstance(answer, str)
    assert "[chunk:ev_01]" in answer


def test_provider_settings_crud_and_test(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        created = client.post(
            "/api/v1/settings/providers",
            json={
                "role": "chat",
                "provider_type": "ollama",
                "model_name": "gemma3:1b",
                "base_url": "http://127.0.0.1:9",
                "is_default": False,
            },
        )
        assert created.status_code == 201
        config_id = created.json()["id"]

        listed = client.get("/api/v1/settings/providers")
        assert listed.status_code == 200
        assert any(item["id"] == config_id for item in listed.json())

        tested = client.post(f"/api/v1/settings/providers/{config_id}/test")
        assert tested.status_code == 200
        assert tested.json()["reachable"] is False

        deleted = client.delete(f"/api/v1/settings/providers/{config_id}")
        assert deleted.status_code == 204

    app.dependency_overrides.clear()


def test_retrieval_falls_back_to_keyword_when_vector_store_unavailable(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={
                "files": (
                    "fallback.md",
                    b"Keyword fallback evidence\n\nAmberstone obligations renew every quarter.",
                    "text/markdown",
                )
            },
        )
        assert upload.status_code == 201
        with patch.object(VectorStore, "query", return_value=[]):
            search = client.post("/api/v1/search", json={"query": "amberstone obligations"})
        assert search.status_code == 200
        assert search.json()["results"]
        assert "Amberstone" in search.json()["results"][0]["snippet"]

    app.dependency_overrides.clear()


def test_corrupted_state_does_not_crash_repository(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{not-json", encoding="utf-8")
    repo = DocumentRepository(tmp_path)
    assert repo.list_documents() == []
