"""Confidence scoring for grounded answers (app/services/rag.py).

The diagnostic confidence breakdown is meant to reflect real uncertainty
(RULE-10) -- a hardcoded OCR component would systematically overstate
confidence for every answer grounded in a scanned document. These pin the
scoring to real per-citation OCR confidence instead.
"""

from __future__ import annotations

from app.domain.models import utc_now
from app.services.rag import score_confidence
from app.services.vector_store import RetrievedChunk

CREATED = utc_now()


def _evidence(evidence_id: str, ocr_confidence: float | None, score: float = 0.8):
    from app.domain.models import Evidence

    return Evidence(
        id=evidence_id,
        document_id="doc_1",
        document_name="lease.pdf",
        section="Section 1",
        page=1,
        line_start=1,
        line_end=3,
        snippet="thirty days notice",
        retrieval_score=score,
        relevance="High",
        ocr_confidence=ocr_confidence,
    )


def test_ocr_component_reflects_low_confidence_citations() -> None:
    """A citation from a poor scan must pull the OCR component down, not sit at 1.0."""
    chunks = [RetrievedChunk(evidence=_evidence("ev_1", ocr_confidence=0.3), score=0.8)]
    breakdown = score_confidence(chunks, cited_ids=["ev_1"])
    assert breakdown.ocr == 0.3
    # The stale hardcoded value must not survive anywhere in the formula.
    assert breakdown.ocr != 1.0


def test_ocr_component_averages_across_multiple_citations() -> None:
    chunks = [
        RetrievedChunk(evidence=_evidence("ev_1", ocr_confidence=0.9), score=0.8),
        RetrievedChunk(evidence=_evidence("ev_2", ocr_confidence=0.5), score=0.7),
    ]
    breakdown = score_confidence(chunks, cited_ids=["ev_1", "ev_2"])
    assert breakdown.ocr == 0.7


def test_ocr_component_is_full_confidence_when_nothing_cited_was_ocrd() -> None:
    """Native text carries no OCR uncertainty at all -- 1.0 here is a fact, not a placeholder."""
    chunks = [RetrievedChunk(evidence=_evidence("ev_1", ocr_confidence=None), score=0.8)]
    breakdown = score_confidence(chunks, cited_ids=["ev_1"])
    assert breakdown.ocr == 1.0


def test_uncited_evidence_does_not_affect_the_ocr_component() -> None:
    """Only the passages actually cited should factor into confidence."""
    chunks = [
        RetrievedChunk(evidence=_evidence("ev_1", ocr_confidence=None), score=0.8),
        RetrievedChunk(evidence=_evidence("ev_2", ocr_confidence=0.1), score=0.2),
    ]
    breakdown = score_confidence(chunks, cited_ids=["ev_1"])
    assert breakdown.ocr == 1.0
