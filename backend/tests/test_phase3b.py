"""Synthetic regressions for Phase 3b; no scorecard fixture content."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.domain.models import Evidence
from app.providers.keyword import KeywordEmbeddingAdapter
from app.providers.ollama import OllamaChatAdapter
from app.repositories.memory import DocumentRepository
from app.services.rag import GroundingGate, RagService, _generate_chat, _query_format_extensions
from app.services.vector_store import RetrievedChunk, VectorStore


def _evidence(key: str, name: str, text: str) -> Evidence:
    return Evidence(
        id=key, document_id=f"doc_{key}", document_name=name, section="Imported content",
        page=1, line_start=1, line_end=1, snippet=text, retrieval_score=0.8, relevance="High",
    )


class _Chat:
    ref = {"provider_type": "ollama", "model_name": "synthetic"}

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompt = ""
        self.schema: dict[str, object] = {}

    def generate(self, prompt: str, *, stream: bool = False, structured_output: dict[str, object]) -> str:
        self.prompt = prompt
        self.schema = structured_output
        return self.answer


class _Registry:
    def __init__(self, chat: _Chat) -> None:
        self.chat = chat

    def get_chat_provider(self) -> _Chat:
        return self.chat

    def get_embedding_provider(self) -> KeywordEmbeddingAdapter:
        return KeywordEmbeddingAdapter()


def _service(tmp_path: Path, units: list[Evidence], chat: _Chat, **settings: object) -> RagService:
    runtime = Settings(data_root=tmp_path, **settings)
    repository = DocumentRepository(tmp_path)
    repository.evidence = {unit.id: unit for unit in units}
    store = VectorStore.__new__(VectorStore)
    store.settings = runtime
    store._available = False
    store._collection = None
    return RagService(runtime, repository, _Registry(chat), store)


def test_ollama_schema_limits_ids_to_displayed_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OllamaChatAdapter(base_url="http://ollama:11434", model_name="synthetic")
    calls: list[dict[str, object]] = []

    def post(path: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        return {"response": '{"answer":"Amber.","evidence_ids":[2]}'}

    monkeypatch.setattr(adapter, "_post_json", post)
    _generate_chat(adapter, "[[chunk:1]]\nFirst.\n[[/chunk]]\n[[chunk:2]]\nSecond.\n[[/chunk]]")
    schema = calls[0]["format"]
    assert schema["properties"]["evidence_ids"]["items"] == {"type": "integer", "enum": [1, 2]}
    assert schema["properties"]["evidence_ids"]["maxItems"] == 2
    assert schema["required"] == ["answer", "evidence_ids"]


@pytest.mark.parametrize("ids", [["VALUE-amber"], [1, 2, 3]])
def test_unknown_passage_ids_are_rejected_without_salvaging_the_answer(ids: list[object]) -> None:
    result = GroundingGate().validate(
        json.dumps({"answer": "The access code is AMBER.", "evidence_ids": ids}), {"1", "2"},
        evidence_by_id={"1": "The access code is AMBER.", "2": "The access code is AMBER."},
        query="What is the access code?",
    )
    assert result.reason == "unknown_evidence_id"
    assert result.outcome == "insufficient_evidence"


def test_truncated_json_has_an_explicit_reason() -> None:
    result = GroundingGate().validate('{"answer":"Amber","evidence_ids":[1', {"1"}, evidence_by_id={"1": "Amber"})
    assert result.reason == "invalid_json"


def test_passage_identity_survives_hint_reordering_and_top_k_cap(tmp_path: Path) -> None:
    note = _evidence("note", "overview.md", "The access code is VIOLET.")
    config = _evidence("config", "settings.json", "The access code is AMBER.")
    chat = _Chat('{"answer":"The access code is AMBER.","evidence_ids":[1]}')
    service = _service(tmp_path, [note, config], chat, ask_max_chunks=1)
    service.retrieve = lambda query, scope=None: [RetrievedChunk(note, 0.9, lexical_coverage=1), RetrievedChunk(config, 0.8, lexical_coverage=1)]
    response = service.ask("What is the access code in the JSON file?")
    assert "[[chunk:1]]\nThe access code is AMBER." in chat.prompt
    assert "VIOLET" not in chat.prompt
    assert response.provider["name"] == "ollama"
    assert [citation.evidence_unit_id for citation in response.citations] == ["config"]


def test_model_cannot_use_text_beyond_the_displayed_passage_cap(tmp_path: Path) -> None:
    unit = _evidence("config", "settings.json", "Overview of access settings. " + "General policy. " * 20 + "The access code is AMBER.")
    chat = _Chat('{"answer":"The access code is AMBER.","evidence_ids":[1]}')
    service = _service(tmp_path, [unit], chat, ask_chunk_max_chars=80)
    service.retrieve = lambda query, scope=None: [RetrievedChunk(unit, 0.9, lexical_coverage=1)]
    response = service.ask("What is the access code in the JSON file?")
    assert "AMBER" not in chat.prompt
    assert response.diagnostic["model_rejected"] == "claim_not_in_evidence"


@pytest.mark.parametrize("word", ["Excel", "xlsx"])
def test_explicit_excel_does_not_accept_csv_even_when_xlsx_is_absent(word: str) -> None:
    assert _query_format_extensions(f"value in the {word.lower()} spreadsheet", {"csv"}) == {"xlsx"}
    csv = _evidence("csv", "budget.csv", "The annual budget is 64 dollars.")
    result = GroundingGate().validate(
        '{"answer":"The annual budget is 64 dollars.","evidence_ids":[1]}', {"1"},
        evidence_by_id={"1": csv.snippet}, evidence_metadata={"1": csv},
        query=f"What is the annual budget in the {word} spreadsheet?",
    )
    assert result.reason == "format_mismatch"


@pytest.mark.parametrize("word", ["spreadsheet", "sheet"])
def test_generic_sheet_allows_csv_but_prefers_xlsx(tmp_path: Path, word: str) -> None:
    csv = _evidence("csv", "budget.csv", "The annual budget is 64 dollars.")
    excel = _evidence("excel", "budget.xlsx", "The annual budget is 42 dollars.")
    service = _service(tmp_path, [csv, excel], _Chat('{"answer":"","evidence_ids":[]}'))
    chunks = service.retrieve(f"What is the annual budget in the {word}?")
    assert [chunk.evidence.document_name for chunk in chunks] == ["budget.xlsx", "budget.csv"]
    result = GroundingGate().validate(
        '{"answer":"The annual budget is 64 dollars.","evidence_ids":[1]}', {"1"},
        evidence_by_id={"1": csv.snippet}, evidence_metadata={"1": csv},
        query=f"What is the annual budget in the {word}?",
    )
    assert result.outcome == "grounded"


def test_explicit_csv_in_a_spreadsheet_question_stays_csv(tmp_path: Path) -> None:
    csv = _evidence("csv", "budget.csv", "The annual budget is 64 dollars.")
    excel = _evidence("excel", "budget.xlsx", "The annual budget is 42 dollars.")
    service = _service(tmp_path, [csv, excel], _Chat('{"answer":"","evidence_ids":[]}'))
    chunks = service.retrieve("What is the annual budget in the CSV spreadsheet?")
    assert [chunk.evidence.document_name for chunk in chunks] == ["budget.csv"]


@pytest.mark.parametrize("word", ["Excel", "xlsx"])
def test_explicit_excel_retrieval_with_both_formats_keeps_only_xlsx(tmp_path: Path, word: str) -> None:
    csv = _evidence("csv", "budget.csv", "The annual budget is 64 dollars.")
    excel = _evidence("excel", "budget.xlsx", "The annual budget is 42 dollars.")
    service = _service(tmp_path, [csv, excel], _Chat('{"answer":"","evidence_ids":[]}'))
    chunks = service.retrieve(f"What is the annual budget in the {word} file?")
    assert [chunk.evidence.document_name for chunk in chunks] == ["budget.xlsx"]
