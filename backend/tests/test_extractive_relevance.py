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


def test_file_format_terms_are_split_and_weighted_across_library_documents() -> None:
    question = "What's the marker value in the YAML config file?"
    chunks = [
        ("ev_yaml", "test_file: 13-config.yaml purpose: structured extraction test marker: YAML-MARKER-2d9b"),
        ("ev_markdown", "# DuckDocs Test File - Markdown This tests plain text/markdown extraction."),
    ]
    frequencies = {
        "test": 2,
        "file": 2,
        "yaml": 1,
        "config": 1,
        "marker": 1,
    }

    evidence_id, sentence = _most_relevant_sentence(question, chunks, frequencies, document_count=2)

    assert evidence_id == "ev_yaml"
    assert "YAML-MARKER-2d9b" in sentence


def test_label_question_prefers_key_value_over_document_title() -> None:
    evidence_id, sentence = _most_relevant_sentence(
        "What is the marker in the JSON file?",
        [
            (
                "ev_json",
                "DuckDocs Test File - JSON Data. This file contains structured values. "
                "marker: JSON-MARKER-4a7c",
            )
        ],
    )

    assert evidence_id == "ev_json"
    assert "JSON-MARKER-4a7c" in sentence


def test_citation_scoring_ignores_format_and_page_descriptors() -> None:
    selected = select_evidence_passage(
        "What is the marker on page 2 of the scanned XML document?",
        "The marker is XML-MARKER-4a7c.",
        "XML document page 2. XML-MARKER-4a7c is the value.",
    )

    assert selected == "XML-MARKER-4a7c is the value"


def test_entity_heading_is_kept_with_adjacent_value_line() -> None:
    selected = select_evidence_passage(
        "What is the location of Kyoto Tower?",
        "Kyoto Tower is located in Kyoto.",
        "Kyoto Tower\nlocated in Kyoto.",
    )

    assert "Kyoto Tower" in selected
    assert "located in Kyoto" in selected


def test_page_hint_does_not_select_a_different_page_marker() -> None:
    evidence_id, sentence = _most_relevant_sentence(
        "What is the marker on page 2 of the scanned document?",
        [("ev_pages", "Page 3 marker: PAGE-3. Page 2 marker: PAGE-2. SCAN-PAGE-3.")],
    )

    assert evidence_id == "ev_pages"
    assert "PAGE-2" in sentence
    assert "PAGE-3" not in sentence


def test_ordinal_page_hint_does_not_select_a_different_page_marker() -> None:
    evidence_id, sentence = _most_relevant_sentence(
        "What does the paragraph on the second page say?",
        [("ev_pages", "Page marker: PAGE-3. Page marker: PAGE-2.")],
    )

    assert evidence_id == "ev_pages"
    assert "PAGE-2" in sentence
    assert "PAGE-3" not in sentence


def test_extraction_prefers_top_retrieved_chunk_when_scores_are_close() -> None:
    evidence_id, sentence = _most_relevant_sentence(
        "What is the test marker in the scanned OCR PDF?",
        [
            ("ocr", "The OCR PDF contains marker SCAN-PDF-9d1c4e."),
            ("multipage", "The scanned multi-page document contains marker SCAN-PAGE-3-b82e."),
        ],
    )

    assert evidence_id == "ocr"
    assert "SCAN-PDF-9d1c4e" in sentence


def test_extraction_matches_marker_inside_ocr_label() -> None:
    _, sentence = _most_relevant_sentence(
        "What is the test marker in the scanned OCR PDF?",
        [("ocr", "DuckDocs Test File. Testmarker:SCAN-PDF-9d1c4e")],
    )

    assert "SCAN-PDF-9d1c4e" in sentence


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


def test_grounding_gate_requires_number_for_count_question() -> None:
    result = GroundingGate().validate(
        "There are several units. [chunk:ev_inventory]",
        {"ev_inventory"},
        evidence_by_id={"ev_inventory": "Widget A is available in stock."},
        query="How many units of Widget A are in stock?",
    )

    assert result.reason == "answer_type_missing"


def test_grounding_gate_accepts_number_for_count_question() -> None:
    result = GroundingGate().validate(
        "There are 12 units. [chunk:ev_inventory]",
        {"ev_inventory"},
        evidence_by_id={"ev_inventory": "Widget A has 12 units in stock."},
        query="How many units of Widget A are in stock?",
    )

    assert result.outcome == "grounded"


def test_grounding_gate_rejects_entity_without_requested_attribute() -> None:
    result = GroundingGate().validate(
        "Priya Nair works here. [chunk:ev_person]",
        {"ev_person"},
        evidence_by_id={"ev_person": "Priya Nair works here."},
        query="What is Priya Nair's department?",
        term_document_frequency={"priya": 1, "nair": 1, "department": 1},
    )

    assert result.reason == "attribute_missing"


def test_grounding_gate_accepts_attribute_with_stemmed_match() -> None:
    result = GroundingGate().validate(
        "Priya Nair is an engineer. [chunk:ev_person]",
        {"ev_person"},
        evidence_by_id={"ev_person": "Priya Nair department: Engineering."},
        query="What is Priya Nair's department?",
        term_document_frequency={"priya": 1, "nair": 1, "department": 1},
    )

    assert result.outcome == "grounded"


def test_grounding_gate_accepts_json_key_value_answer() -> None:
    evidence = _json_evidence = type(
        "JsonEvidence", (), {"document_name": "config.json"}
    )()
    result = GroundingGate().validate(
        "The status is active. [chunk:ev_json]",
        {"ev_json"},
        evidence_by_id={"ev_json": '"status": "active"'},
        evidence_metadata={"ev_json": evidence},
    )

    assert result.outcome == "grounded"


def test_json_value_citation_selects_key_value_line() -> None:
    selected = select_evidence_passage(
        "What is the status value in the JSON document?",
        "The status is active.",
        '{"status": "active", "owner": "local"}',
    )

    assert "active" in selected


def test_value_question_prefers_label_value_after_leading_sentences() -> None:
    selected = select_evidence_passage(
        "What is the value of status in the JSON document?",
        "The status is active.",
        "Configuration heading. First paragraph explains the file. status: active.",
    )

    assert "status: active" in selected


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
