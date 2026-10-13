import json
from uuid import uuid4

import pytest

from app.services.page_queries import ordinal_number, parse_page_reference
from app.services.rag import GroundingGate
from app.services.vector_store import RetrievedChunk, VectorStore
from tests.test_phase3b import _Chat, _evidence, _service


@pytest.mark.parametrize("text,number", [
    ("first", 1), ("second", 2), ("12th", 12), ("twenty-first", 21),
    ("ninety ninth", 99), ("one hundred and first", 101), ("one hundred first", 101), ("0th", None),
])
def test_generic_number_parser(text, number):
    assert ordinal_number(text) == number


@pytest.mark.parametrize("phrase,page", [
    ("on the second page", 2), ("page 2", 2), ("page number two", 2),
    ("the twenty-first page", 21), ("21st page", 21), ("page no. 12", 12),
    ("after the page break", 2), ("after the third page break", 4),
    ("the last page", 27), ("the final slide", 27),
])
def test_page_words_use_one_parser(phrase, page):
    assert parse_page_reference(phrase).resolve(27) == page


@pytest.mark.parametrize("phrase", ["page 0", "page 2 and page 3"])
def test_invalid_or_conflicting_page_request_cannot_select_a_page(phrase):
    assert parse_page_reference(phrase).resolve(9) is None


@pytest.mark.parametrize("extension", ["docx", "pdf", "pptx"])
@pytest.mark.parametrize("phrase", ["second page", "page 2", "after the page break"])
def test_page_filter_applies_before_fusion_even_when_vector_ranking_is_wrong(tmp_path, extension, phrase):
    wrong = _evidence("wrong", f"manual.{extension}", "The access code is AMBER.").model_copy(update={"document_id": "doc_manual", "page": 1})
    right = _evidence("right", f"manual.{extension}", "The access code is CEDAR.").model_copy(update={"document_id": "doc_manual", "page": 2})
    service = _service(tmp_path, [wrong, right], _Chat('{"answer":"The access code is CEDAR.","evidence_ids":[1]}'))
    service.vector_store.query = lambda *args, **kwargs: [RetrievedChunk(wrong, 1.0), RetrievedChunk(right, 0.7)]
    chunks = service.retrieve(f"What is the access code on the {phrase} of manual.{extension}?")
    assert [c.evidence.id for c in chunks] == ["right"]


def test_last_page_resolves_per_document_from_all_evidence(tmp_path):
    units = [_evidence(f"a{n}", "alpha.pdf", "Access code is AMBER.").model_copy(update={"document_id": "a", "page": n}) for n in (1, 2)]
    units += [_evidence(f"b{n}", "beta.docx", "Access code is BIRCH.").model_copy(update={"document_id": "b", "page": n}) for n in (1, 2, 3)]
    service = _service(tmp_path, units, _Chat('{"answer":"","evidence_ids":[]}'))
    assert service._hint_candidate_ids("What is the access code on the last page?", None) == {"a2", "b3"}


def test_gate_rejects_wrong_ordinal_page_even_if_the_words_support_the_answer():
    evidence = _evidence("wrong", "manual.docx", "Access code: CEDAR.")
    result = GroundingGate().validate(json.dumps({"answer": "Access code: CEDAR.", "evidence_ids": [1]}), {"1"},
        evidence_by_id={"1": evidence.snippet}, evidence_metadata={"1": evidence}, query="What is the access code on the second page?")
    assert result.outcome == "insufficient_evidence"
    assert result.reason == "format_mismatch"


def test_last_page_gate_uses_document_total_not_the_retrieved_subset():
    evidence = _evidence("wrong", "manual.pdf", "Access code: CEDAR.").model_copy(update={"page": 2})
    result = GroundingGate().validate('{"answer":"Access code: CEDAR.","evidence_ids":[1]}', {"1"},
        evidence_by_id={"1": evidence.snippet}, evidence_metadata={"1": evidence},
        query="What is the access code on the last page?", document_pages={evidence.document_id: 3})
    assert result.outcome == "insufficient_evidence"


def test_slide_ordinals_restrict_to_presentation_pages(tmp_path):
    units = [_evidence(ext, f"manual.{ext}", "Access code: CEDAR.").model_copy(update={"page": 3}) for ext in ("docx", "pdf", "pptx")]
    service = _service(tmp_path, units, _Chat('{"answer":"","evidence_ids":[]}'))
    assert service._hint_candidate_ids("What is the access code on the third slide?", None) == {"pptx"}


def test_named_document_page_does_not_include_other_documents(tmp_path):
    units = [_evidence(name, name + ".docx", "Access code: CEDAR.").model_copy(update={"page": 2}) for name in ("alpha", "beta")]
    service = _service(tmp_path, units, _Chat('{"answer":"","evidence_ids":[]}'))
    assert service._hint_candidate_ids("What is the access code on page 2 of alpha.docx?", None) == {"alpha"}


def test_empty_last_page_does_not_substitute_the_last_page_with_evidence(tmp_path):
    from types import SimpleNamespace
    unit = _evidence("body", "report.docx", "Access code: CEDAR.").model_copy(update={"page": 2})
    service = _service(tmp_path, [unit], _Chat('{"answer":"","evidence_ids":[]}'))
    service.repository.documents[unit.document_id] = SimpleNamespace(id=unit.document_id, pages=3)
    assert service._hint_candidate_ids("What is the access code on the last page?", None) == set()


def test_chroma_page_filter_precedes_top_k_and_similarity_cut(tmp_path):
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from app.core.config import Settings
    class Embedder:
        ref = {"provider_type": "synthetic", "model_name": "test"}
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]
    store = VectorStore.__new__(VectorStore)
    store.settings = Settings(data_root=tmp_path)
    store._available = True
    client = chromadb.EphemeralClient(settings=ChromaSettings(anonymized_telemetry=False))
    store._collection = client.create_collection("pages_" + uuid4().hex, metadata={"hnsw:space": "cosine"})
    units = [_evidence(str(i), "report.pdf", "Access code: CEDAR.").model_copy(update={"document_id": "doc", "page": i + 1}) for i in range(20)]
    assert store.upsert_evidence(units, Embedder()) == 20
    found = store.query("Access code", Embedder(), {e.id: e for e in units}, top_k=1, min_similarity=0.1,
                        document_ids=["doc"], page_constraints={"doc": 17})
    assert [c.evidence.page for c in found] == [17]
