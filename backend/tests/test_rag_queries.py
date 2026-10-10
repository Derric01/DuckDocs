from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.domain.models import Evidence
from app.repositories.memory import DocumentRepository
from app.services.rag import RagService
from app.services.vector_store import RetrievedChunk, VectorStore


class _Chat:
    ref = {
        "role": "chat",
        "provider_type": "extractive",
        "model_name": "test-chat",
        "base_url": None,
        "config_id": "test-chat",
    }

    def generate(self, prompt: str, *, stream: bool = True) -> str:
        import re

        ids = re.findall(r"\[\[chunk:([^\]]+)\]\]", prompt)
        if not ids:
            return "INSUFFICIENT_EVIDENCE"
        return "The answer is supported by the retrieved rows " + " ".join(
            f"[chunk:{evidence_id}]" for evidence_id in ids
        ) + "."


class _Registry:
    def __init__(self, chat=None) -> None:  # type: ignore[no-untyped-def]
        from app.providers.keyword import KeywordEmbeddingAdapter

        self.chat = chat or _Chat()
        self.embedding = KeywordEmbeddingAdapter()

    def get_chat_provider(self) -> _Chat:
        return self.chat

    def get_embedding_provider(self):  # type: ignore[no-untyped-def]
        return self.embedding


def _evidence(evidence_id: str, document_name: str, snippet: str) -> Evidence:
    return Evidence(
        id=evidence_id,
        document_id=f"doc_{document_name}",
        document_name=document_name,
        section="Imported content",
        page=1,
        line_start=1,
        line_end=4,
        snippet=snippet,
        retrieval_score=0.74,
        relevance="Medium",
    )


def _service(evidence: list[Evidence]) -> RagService:
    repo = DocumentRepository(Path("test-data"))
    repo.evidence = {item.id: item for item in evidence}
    settings = Settings(data_root=Path("test-data"), top_k=12)
    registry = _Registry()
    vector_store = VectorStore(settings)
    vector_store._available = False
    return RagService(settings, repo, registry, vector_store)


class _SynthesisChat(_Chat):
    def generate(self, prompt: str, *, stream: bool = True) -> str:
        import re

        chunk_id = re.search(r"\[\[chunk:([^\]]+)\]\]", prompt).group(1)  # type: ignore[union-attr]
        if "revenue" in prompt.lower():
            return f"The total revenue is 37300. [chunk:{chunk_id}]"
        return f"The scanned document contains OCR text about a rendered image. [chunk:{chunk_id}]"


def test_single_document_factual_lookup_returns_grounded_answer() -> None:
    service = _service([_evidence("ev_priya", "09-data.csv", "Priya Nair, Engineering")])

    response = service.ask("What is the department of Priya Nair?")

    assert response.outcome == "grounded"
    assert response.citations[0].evidence_unit_id == "ev_priya"
    assert response.diagnostic["top_score"] > 0


def test_numeric_aggregation_query_keeps_multiple_supporting_rows() -> None:
    service = _service(
        [
            _evidence("ev_a", "09-data.csv", "Priya Nair, Engineering, 12"),
            _evidence("ev_b", "09-data.csv", "Arun Shah, Engineering, 18"),
        ]
    )

    response = service.ask("What is the total of the Engineering values across the rows?")

    assert response.outcome == "grounded"
    assert response.citations
    assert all(citation.snippet for citation in response.citations)


def test_explicit_filename_query_prioritizes_named_document() -> None:
    service = _service(
        [
            _evidence("ev_csv", "09-data.csv", "Priya Nair, Engineering"),
            _evidence("ev_notes", "meeting-notes.md", "Priya Nair discussed hiring."),
        ]
    )

    chunks = service.retrieve("In 09-data.csv, what is the department of Priya Nair?")

    assert chunks
    assert chunks[0].evidence.document_name == "09-data.csv"
    assert chunks[0].evidence.retrieval_score > chunks[1].evidence.retrieval_score


def test_question_without_supporting_evidence_refuses() -> None:
    service = _service([_evidence("ev_priya", "09-data.csv", "Priya Nair, Engineering")])

    response = service.ask("What is the office location of Morgan Lee?")

    assert response.outcome == "insufficient_evidence"
    assert response.answer is None
    assert response.citations == []


def test_duckdocs_pricing_question_without_supporting_evidence_refuses() -> None:
    service = _service([_evidence("ev_native", "01-native-text.pdf", "DuckDocs has a selectable text layer.")])

    response = service.ask("What is DuckDocs' pricing model?")

    assert response.outcome == "insufficient_evidence"
    assert response.answer is None
    assert response.citations == []


def test_scanned_filename_query_retrieves_sparse_ocr_document() -> None:
    service = _service(
        [
            _evidence(
                "ev_ocr",
                "02-scanned-ocr.pdf",
                "DuckDocs Test File - Scanned PDF (OCR) This page has no text layer.",
            )
        ]
    )

    chunks = service.retrieve("What does 02-scanned-ocr.pdf say?")

    assert len(chunks) == 1
    assert chunks[0].evidence.document_name == "02-scanned-ocr.pdf"


def test_reciprocal_rank_fusion_keeps_keyword_only_hit() -> None:
    vector_evidence = _evidence("ev_vector", "notes.md", "A semantic reference to the requested topic.")
    keyword_evidence = _evidence("ev_keyword", "13-config.yaml", "YAML config file marker: YAML-MARKER-2d9b")
    service = _service([vector_evidence, keyword_evidence])
    service.vector_store.query = lambda *args, **kwargs: [RetrievedChunk(vector_evidence, 0.9)]  # type: ignore[method-assign]

    chunks = service.retrieve("What is the marker value in the YAML config file?")

    assert {chunk.evidence.id for chunk in chunks} == {"ev_vector", "ev_keyword"}


def test_document_hints_reject_wrong_format_and_page_citations() -> None:
    service = _service(
        [
            _evidence("ev_yaml", "13-config.yaml", "YAML config file marker: YAML-MARKER-2d9b"),
            _evidence("ev_markdown", "12-notes.md", "Marker: MD-MARKER-8e41"),
        ]
    )
    yaml_chunks = service.retrieve("What's the marker value in the YAML config file?")
    assert yaml_chunks[0].evidence.document_name == "13-config.yaml"

    service = _service([_evidence("ev_scanned", "03-scanned-multipage.pdf", "Page marker: SCAN-PAGE-2-b82e")])
    response = service.ask("What is the marker on page 2 of the scanned multi-page document?")
    assert response.outcome == "insufficient_evidence"


def test_revenue_sum_is_grounded_as_synthesized_answer() -> None:
    service = _service(
        [
            _evidence(
                "ev_revenue",
                "07-spreadsheet.xlsx",
                "Sheet: Sales Month | Revenue | Units Jan | 12000 | 340 Feb | 15500 | 410 Mar | 9800 | 265",
            )
        ]
    )
    service.registry.chat = _SynthesisChat()

    response = service.ask("What is the total revenue for Jan, Feb, and Mar?")

    assert response.outcome == "grounded"
    assert response.answer == "The total revenue is 37300."
    assert response.citations[0].evidence_unit_id == "ev_revenue"


def test_semantic_vector_hit_is_not_discarded_for_lacking_exact_query_terms() -> None:
    evidence = _evidence(
        "ev_climate",
        "kyoto-guide.pdf",
        "Early summer brings persistent precipitation and uncomfortable humidity.",
    )
    service = _service([evidence])
    service.vector_store.query = lambda *args, **kwargs: [RetrievedChunk(evidence, 0.82)]  # type: ignore[method-assign]

    chunks = service.retrieve("Why is the rainy season uncomfortable?")

    assert [chunk.evidence.id for chunk in chunks] == ["ev_climate"]


def test_failed_document_reindex_does_not_delete_existing_vectors() -> None:
    service = _service([_evidence("ev_retention", "policy.pdf", "Falcon records stay local for 18 months.")])

    class _Store:
        def __init__(self) -> None:
            self.deleted = False

        def upsert_evidence(self, units, embedder):  # type: ignore[no-untyped-def]
            return 0

        def delete_document(self, document_id, *, keep_ids=None):  # type: ignore[no-untyped-def]
            self.deleted = True

    store = _Store()
    service.vector_store = store  # type: ignore[assignment]

    assert service.index_document("doc_policy.pdf") == 0
    assert not store.deleted


def test_successful_document_reindex_removes_only_stale_vectors() -> None:
    service = _service([_evidence("ev_retention", "policy.pdf", "Falcon records stay local for 18 months.")])

    class _Store:
        def __init__(self) -> None:
            self.deleted_with: set[str] | None = None

        def upsert_evidence(self, units, embedder):  # type: ignore[no-untyped-def]
            return len(units)

        def delete_document(self, document_id, *, keep_ids=None):  # type: ignore[no-untyped-def]
            self.deleted_with = keep_ids

    store = _Store()
    service.vector_store = store  # type: ignore[assignment]

    assert service.index_document("doc_policy.pdf") == 1
    assert store.deleted_with == {"ev_retention"}
