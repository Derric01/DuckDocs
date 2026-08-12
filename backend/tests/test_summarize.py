"""Ingest-time summarization tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.main import app
from app.services.parsing import ParsedDocument, ParsedPage
from app.services.summarize import (
    MAX_SUMMARY_SENTENCES,
    build_summary_prompt,
    clean_model_summary,
    summarize_extractive,
)
from tests.test_ingestion import client_with_data_root

BODY = (
    "Falcon records must stay on the local machine for 18 months before archival review. "
    "The compliance team audits retention adherence on a quarterly basis. "
    "Exceptions to the retention window require written approval from the data steward. "
    "Archived records are moved to cold storage and retained for a further five years. "
    "All access to archived records is logged and reviewed annually by the security team."
)


def _parsed(text: str) -> ParsedDocument:
    return ParsedDocument(pages=[ParsedPage(1, text, "native")], fidelity_tier="full_layout", page_count=1)


def test_extractive_summary_uses_only_verbatim_sentences() -> None:
    summary = summarize_extractive(_parsed(BODY))
    assert summary.method == "extractive"
    assert summary.text
    # Every sentence must appear in the source: an extractive summary that
    # invents wording would break the product's provenance guarantee.
    for sentence in summary.text.split(". "):
        stripped = sentence.strip().rstrip(".")
        if stripped:
            assert stripped in BODY


def test_extractive_summary_is_bounded_even_for_short_documents() -> None:
    # A char budget alone returns a short document in full; the sentence cap
    # is what keeps it recognizable as a summary.
    summary = summarize_extractive(_parsed(BODY))
    sentence_count = len([part for part in summary.text.split(".") if part.strip()])
    assert sentence_count <= MAX_SUMMARY_SENTENCES


def test_extractive_summary_respects_char_budget() -> None:
    long_text = " ".join(f"Sentence number {index} carries meaningful policy content here." for index in range(200))
    summary = summarize_extractive(_parsed(long_text), max_chars=200)
    assert len(summary.text) <= 220


def test_extractive_summary_collapses_whitespace() -> None:
    summary = summarize_extractive(_parsed("Heading here\n\n\n" + BODY))
    assert "\n" not in summary.text
    assert "  " not in summary.text


def test_summary_handles_text_without_sentences() -> None:
    summary = summarize_extractive(_parsed("col_a | col_b | col_c"))
    assert summary.method == "extractive"
    assert isinstance(summary.text, str)


def test_summary_prompt_includes_title_and_body() -> None:
    prompt = build_summary_prompt("policy.pdf", _parsed(BODY))
    assert "policy.pdf" in prompt
    assert "Falcon records" in prompt
    assert "do not speculate" in prompt


@pytest.mark.parametrize(
    ("raw", "expected_start"),
    [
        ("Summary: The document covers retention.", "The document covers retention."),
        ("  Multiple   spaces   collapse.  ", "Multiple spaces collapse."),
    ],
)
def test_clean_model_summary_normalizes_output(raw: str, expected_start: str) -> None:
    assert clean_model_summary(raw) == expected_start


def test_clean_model_summary_truncates_at_a_sentence_boundary() -> None:
    text = "First sentence is here. " + ("padding words " * 100)
    cleaned = clean_model_summary(text, max_chars=60)
    assert len(cleaned) <= 61
    assert cleaned.endswith(".") or cleaned.endswith("…")


# --- pipeline ------------------------------------------------------------


def test_upload_produces_a_summary(tmp_path: Path) -> None:
    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"files": ("retention.md", f"Retention Policy\n\n{BODY}".encode(), "text/markdown")},
        )
        document_id = upload.json()["items"][0]["document"]["id"]

        document = client.get(f"/api/v1/documents/{document_id}").json()
        assert document["status"] == "ready"
        assert document["summary"]
        # With no chat provider connected, the offline path must still yield a
        # summary rather than leaving the field empty.
        assert document["summary_method"] == "extractive"
        assert "Falcon records" in document["summary"] or "compliance" in document["summary"]

    app.dependency_overrides.clear()


def test_summarization_failure_does_not_fail_ingest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import summarize as summarize_module

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("summarizer exploded")

    monkeypatch.setattr(summarize_module, "summarize_extractive", _explode)

    with client_with_data_root(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"files": ("retention.md", BODY.encode(), "text/markdown")},
        )
        assert upload.status_code == 201

    app.dependency_overrides.clear()
