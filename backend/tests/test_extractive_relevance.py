from __future__ import annotations

from app.providers.extractive import _most_relevant_sentence
from app.services.rag import GroundingGate, select_evidence_passage


def test_why_question_prefers_relevant_climate_warning_sentence() -> None:
    query = "Why is June not recommended for visiting Kyoto according to the document?"
    climate = (
        "Kyoto's climate has hot and humid summers. The wettest month is June with 14d of rainfall. "
        "Warning: Avoid traveling during the wettest months (June) and hottest months (July and August), "
        "as the heat and humidity can be overwhelming."
    )

    _, sentence = _most_relevant_sentence(query, [("ev_climate", climate)])

    assert sentence.startswith("Warning: Avoid traveling")


def test_warning_heading_splits_flattened_pdf_text_for_answer_selection() -> None:
    query = "Why is June not recommended for visiting Kyoto according to the document?"
    flattened = (
        "Best months October, May, June Avoid July, August, September "
        "Warning: Avoid traveling during the wettest months (June) and hottest months (July and August), "
        "as the heat and humidity can be overwhelming."
    )

    _, sentence = _most_relevant_sentence(query, [("ev_climate", flattened)])

    assert sentence.startswith("Warning: Avoid traveling")


def test_why_question_can_select_cause_from_a_lower_ranked_chunk() -> None:
    question = "Why did the Hare lose the race?"
    chunks = [
        ("ev_finish", "The Hare woke and ran faster, but the Tortoise crossed the finish line first."),
        (
            "ev_cause",
            "The overconfident Hare decided to take a nap, assuming he had plenty of time. "
            "While the Hare fell into a deep sleep, the Tortoise kept moving steadily.",
        ),
    ]

    evidence_id, sentence = _most_relevant_sentence(question, chunks)

    assert evidence_id == "ev_cause"
    assert "nap" in sentence or "sleep" in sentence


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


def test_citation_selects_only_kyoto_climate_sentences() -> None:
    query = "Why is June not recommended for visiting Kyoto according to the document?"
    snippet = (
        "The food section recommends Yudofu Sagano. Kyoto's climate has hot and humid summers. "
        "The wettest month is June with 14d of rainfall. Warning: Avoid traveling during the wettest months "
        "(June) and hottest months (July and August), as the heat and humidity can be overwhelming."
    )
    selected = select_evidence_passage(
        query,
        "June is not recommended because it is the wettest month with 14 days of rainfall, and the document "
        "warns travelers to avoid wettest months due to heat and humidity.",
        snippet,
    )

    assert "wettest month is June" in selected
    assert "Avoid traveling during the wettest months" in selected
    assert "Avoid July" not in selected
    assert "heat and humidity can be overwhelming" in selected
    assert "Yudofu" not in selected
    assert "hot and humid summers" not in selected


def test_citation_selects_restaurant_entry_without_neighboring_description() -> None:
    snippet = (
        "Food & Dining. Yudofu Sagano $$ · Arashiyama — Order the Yudofu — "
        "A popular spot for boiled tofu, often served with dipping sauces and side dishes."
    )
    selected = select_evidence_passage(
        "What is the recommended restaurant for Yudofu?",
        "The recommended restaurant is Yudofu Sagano in Arashiyama.",
        snippet,
    )

    assert selected == "Yudofu Sagano $$ · Arashiyama — Order the Yudofu"
    assert "Food & Dining" not in selected
    assert "A popular spot" not in selected


def test_hare_tortoise_citation_selects_supporting_sentence_only() -> None:
    snippet = (
        "The Hare ran quickly at first and soon left the Tortoise behind. "
        "Confident he would win, the Hare stopped to rest and fell asleep. "
        "The Tortoise continued at a steady pace and crossed the finish line first."
    )
    selected = select_evidence_passage(
        "Why did the Hare lose the race?",
        "The Hare lost because he stopped to rest and fell asleep.",
        snippet,
    )

    assert selected == "the Hare stopped to rest and fell asleep"
    assert "Confident" not in selected
    assert "Tortoise" not in selected


def test_citation_includes_answer_supporting_causal_clause() -> None:
    snippet = (
        "Feeling completely secure in his massive lead, the overconfident hare decided to take a quick nap "
        "in the cool shade of a large tree, assuming he had plenty of time to rest before his opponent could catch up. "
        "While the hare fell into a deep sleep, the tortoise kept moving steadily."
    )
    selected = select_evidence_passage(
        "Why did the Hare lose the race?",
        "The overconfident hare lost because he decided to take a quick nap, assuming he had plenty of time to rest.",
        snippet,
    )

    assert "quick nap" in selected
    assert "assuming he had plenty of time to rest" in selected
    assert "woke" not in selected
    assert "tortoise" not in selected


def test_unrelated_restaurant_row_does_not_get_a_quote_for_yudofu() -> None:
    selected = select_evidence_passage(
        "What is the recommended restaurant for Yudofu?",
        "The recommended restaurant is Gion Nanba.",
        "Recommended restaurants Gion Nanba — Order the Kaiseki.",
    )

    assert selected == ""
