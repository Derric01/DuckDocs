from __future__ import annotations

from app.providers.extractive import _most_relevant_sentence
from app.services.rag import GroundingGate


def test_why_question_prefers_relevant_climate_warning_sentence() -> None:
    query = "Why is June not recommended for visiting Kyoto according to the document?"
    climate = (
        "Kyoto's climate has hot and humid summers. The wettest month is June with 14d of rainfall. "
        "Warning: Avoid traveling during the wettest months (June) and hottest months (July and August), "
        "as the heat and humidity can be overwhelming."
    )

    _, sentence = _most_relevant_sentence(query, [("ev_climate", climate)])

    assert sentence.startswith("Warning: Avoid traveling")


def test_grounding_gate_checks_six_word_factual_claims() -> None:
    result = GroundingGate().validate(
        "The record identifies the Engineering department. [chunk:ev_climate]",
        {"ev_climate"},
        evidence_by_id={"ev_climate": "Kyoto's wettest month is June with 14 days of rainfall."},
    )

    assert result.outcome == "insufficient_evidence"
    assert result.reason == "content_not_grounded"


def test_grounding_gate_checks_short_cited_claims() -> None:
    result = GroundingGate().validate(
        "I am DuckDocs Waymark. [chunk:ev_climate]",
        {"ev_climate"},
        evidence_by_id={"ev_climate": "Kyoto's wettest month is June with 14 days of rainfall."},
    )

    assert result.outcome == "insufficient_evidence"
    assert result.reason == "content_not_grounded"
