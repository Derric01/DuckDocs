from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.chunking import chunk_document
from app.services.parsing import ParsedDocument, ParsedPage


def test_long_single_line_page_is_split_with_overlap_and_bounded_size() -> None:
    settings = Settings(
        data_root=Path("test-data"),
        chunk_max_words=100,
        chunk_overlap_words=20,
    )
    text = " ".join(f"word{index}" for index in range(250))
    parsed = ParsedDocument(
        pages=[ParsedPage(1, text, "native", None)],
        fidelity_tier="full_layout",
        page_count=1,
    )

    chunks = chunk_document(parsed, settings)

    assert [len(chunk.text.split()) for chunk in chunks] == [100, 100, 90]
    assert chunks[0].text.split()[-20:] == chunks[1].text.split()[:20]
    assert chunks[1].text.split()[-20:] == chunks[2].text.split()[:20]
