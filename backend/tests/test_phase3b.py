"""Synthetic regressions for Phase 3b; no scorecard fixture content."""
from __future__ import annotations

import json
import io
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from app.core.config import Settings
from app.domain.models import Evidence
from app.providers.keyword import KeywordEmbeddingAdapter
from app.providers.ollama import OllamaChatAdapter
from app.repositories.memory import DocumentRepository
from app.services.rag import GroundingGate, RagService, _answer_type_missing, _generate_chat, _query_format_extensions
from app.providers.extractive import _most_relevant_sentence
from app.services.chunking import chunk_document
from app.services.parsing import parse_docx
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


def test_json_key_lookup_survives_unavailable_vectors(tmp_path: Path) -> None:
    unit = _evidence("config", "service-settings.json", '{"beacon": "SIGNAL-842", "owner": "local"}')
    note = _evidence("note", "overview.md", "A general description of service settings.")
    chat = _Chat('{"answer":"The beacon is SIGNAL-842.","evidence_ids":[1]}')
    service = _service(tmp_path, [unit, note], chat)
    chunks = service.retrieve("What's the beacon value in the JSON file?")
    assert [chunk.evidence.id for chunk in chunks] == ["config"]
    response = service.ask("What's the beacon value in the JSON file?")
    assert response.outcome == "grounded"
    assert "SIGNAL-842" in response.answer
    assert [citation.evidence_unit_id for citation in response.citations] == ["config"]


def test_explicit_format_with_no_candidate_does_not_search_other_documents(tmp_path: Path) -> None:
    unit = _evidence("note", "overview.md", "The beacon is SIGNAL-842.")
    service = _service(tmp_path, [unit], _Chat('{"answer":"","evidence_ids":[]}'))
    assert service._hint_candidate_ids("What is the beacon in the JSON file?", None) == set()
    assert service.retrieve("What is the beacon in the JSON file?") == []


def test_compound_term_matching_keeps_explicit_filename_lookup() -> None:
    assert RagService._has_lexical_support("What does service-settings.json say?", '{"beacon":"local"}', "service-settings.json")


def test_cited_source_json_is_validated_as_evidence_not_a_model_envelope() -> None:
    unit = _evidence("config", "settings.json", '{"beacon":"SIGNAL-842","owner":"local"}')
    result = GroundingGate().validate(
        unit.snippet + " [chunk:1].", {"1"}, evidence_by_id={"1": unit.snippet},
        evidence_metadata={"1": unit}, query="What is the beacon value in the JSON file?",
    )
    assert result.outcome == "grounded"


@pytest.mark.parametrize("query", [
    "In dollars, what is the admission fee according to this guide?",
    "What does the guide say about admission, including its cost in euros?",
    "For admission, tell me the listed price expressed in INR.",
    "How much in pounds is admission listed as?",
    "What do visitors pay for admission in USD?",
    "What is the admission charge in yen?",
])
def test_amount_questions_check_the_selected_quote_not_unrelated_numbers(query: str) -> None:
    source = "Admission is listed below. Revision number: 2024. The cafe serves lunch."
    result = GroundingGate().validate(
        '{"answer":"Admission is listed below.","evidence_ids":[1]}', {"1"},
        evidence_by_id={"1": source}, query=query,
    )
    assert result.reason == "answer_type_missing"


@pytest.mark.parametrize("source", ["Entry fee: USD42.", "Entry fee: € 42.50.", "Entry fee: 2,500 rupees."])
def test_amount_questions_accept_numeric_currency_evidence(source: str) -> None:
    assert not _answer_type_missing("What is the entry fee in currency?", ["1"], {"1": source}, source)


def test_non_amount_currency_question_is_not_forced_to_have_a_number() -> None:
    assert not _answer_type_missing("Which currency is accepted?", ["1"], {"1": "The accepted currency is euros."})


def _docx(paragraphs: list[str]) -> bytes:
    buffer = io.BytesIO()
    body = "".join(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" for text in paragraphs)
    document = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + "</w:body></w:document>"
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        package.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        package.writestr("word/document.xml", document)
    return buffer.getvalue()


@pytest.mark.parametrize("question", [
    "What's the audit reference value in the Word document?",
    "Tell me the value of the audit reference in this document.",
    "What is the audit reference?",
])
def test_docx_label_value_wins_over_heading_and_first_paragraph(tmp_path: Path, question: str) -> None:
    payload = _docx([
        "Audit reference report.", "Audit reference section.",
        "This first paragraph explains the audit reference report and its purpose.",
        "Audit reference: REF-CEDAR-572.",
    ])
    parsed = parse_docx(payload)
    assert parsed is not None
    chunks = chunk_document(parsed, Settings())
    unit = _evidence("report", "audit.docx", chunks[0].text)
    _, sentence = _most_relevant_sentence(question, [(unit.id, unit.snippet)])
    assert sentence == "Audit reference: REF-CEDAR-572."
    service = _service(tmp_path, [unit], _Chat('{"answer":"","evidence_ids":[]}'))
    response = service.ask(question)
    assert response.outcome == "grounded"
    assert response.answer == "Audit reference: REF-CEDAR-572."
    assert response.citations[0].snippet == "Audit reference: REF-CEDAR-572"
    assert response.citations[0].snippet in unit.snippet


def test_label_selection_does_not_choose_a_different_property() -> None:
    _, sentence = _most_relevant_sentence(
        "What is the audit reference?",
        [("report", "Audit reference report. Audit owner: Morgan. Audit reference: REF-CEDAR-572.")],
    )
    assert "REF-CEDAR-572" in sentence
    assert "Morgan" not in sentence


@pytest.mark.parametrize("answer", ["Page identifier.", "Document identifier.", "PDF."])
def test_model_label_only_answers_do_not_gain_information_from_format_words(answer: str) -> None:
    result = GroundingGate().validate(
        json.dumps({"answer": answer, "evidence_ids": [1]}), {"1"},
        evidence_by_id={"1": "The page identifier is RELEASE-CEDAR-701."},
        query="What is the release identifier in the scanned PDF?",
    )
    assert result.reason == "content_not_informative"


def test_model_identifier_value_still_adds_information() -> None:
    result = GroundingGate().validate(
        '{"answer":"RELEASE-CEDAR-701","evidence_ids":[1]}', {"1"},
        evidence_by_id={"1": "The identifier is RELEASE-CEDAR-701."},
        query="What is the release identifier?",
    )
    assert result.outcome == "grounded"
