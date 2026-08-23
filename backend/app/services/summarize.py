"""Document summarization at ingest time.

A summary is *generated* text, not retrieved evidence, so it is held to the
same honesty rule as everything else: the method that produced it is stored
alongside it and surfaced in the UI. Two methods exist.

`extractive` picks the most representative sentences already present in the
document and returns them verbatim. Nothing is invented, so it is safe to
show without a model and is the default offline path.

`abstractive` asks the configured chat provider to write a summary. It reads
better, but it is model output — the UI labels it as such.

Summarization never fails ingestion: if a provider errors or is unreachable,
the extractive result stands in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.parsing import ParsedDocument

SummaryMethod = Literal["extractive", "abstractive"]

# Enough to characterize a document without turning the library into a wall
# of text; the full document is one click away.
MAX_SUMMARY_CHARS = 600
MAX_PROMPT_CHARS = 6000
# A character budget alone returns a short document in full, which reads as a
# dump rather than a summary. Capping sentences keeps the shape of a summary
# regardless of document length.
MAX_SUMMARY_SENTENCES = 3

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")

# Ranking by term frequency alone promotes sentences full of filler, so the
# most common English function words are excluded from the score.
_STOPWORDS = frozenset(
    """a an and are as at be been but by for from had has have he her his i in is it its of on or
    that the their there they this to was were which who will with would you your our we us not
    can could should may might do does did done than then them these those such into over under
    about after before between during if each other some more most only same so too very""".split()
)


@dataclass(slots=True)
class DocumentSummary:
    text: str
    method: SummaryMethod
    provider: str | None = None


def _sentences(text: str) -> list[str]:
    candidates = [sentence.strip() for sentence in _SENTENCE_SPLIT.split(text) if sentence.strip()]
    # Drop fragments that are almost certainly headings, page numbers, or
    # table cells rather than prose.
    return [sentence for sentence in candidates if len(sentence.split()) >= 5]


def summarize_extractive(
    parsed: ParsedDocument,
    max_chars: int = MAX_SUMMARY_CHARS,
    max_sentences: int = MAX_SUMMARY_SENTENCES,
) -> DocumentSummary:
    """Select representative sentences verbatim from the document.

    Sentences are scored by how much of the document's own vocabulary they
    carry, then emitted in original document order so the result reads as a
    passage rather than a shuffled list.
    """
    full_text = "\n".join(page.text for page in parsed.pages if page.text).strip()
    sentences = _sentences(full_text)

    if not sentences:
        # Nothing sentence-like: fall back to the opening of the raw text so
        # the card still says something true about the file.
        condensed = re.sub(r"\s+", " ", full_text)[:max_chars].strip()
        return DocumentSummary(text=condensed, method="extractive")

    frequencies: dict[str, int] = {}
    for word in _WORD.findall(full_text.lower()):
        if word in _STOPWORDS:
            continue
        frequencies[word] = frequencies.get(word, 0) + 1

    def score(sentence: str) -> float:
        words = [word for word in _WORD.findall(sentence.lower()) if word not in _STOPWORDS]
        if not words:
            return 0.0
        # Mean rather than sum, so a long sentence does not win on length alone.
        return sum(frequencies.get(word, 0) for word in words) / len(words)

    ranked = sorted(range(len(sentences)), key=lambda index: score(sentences[index]), reverse=True)

    chosen: list[int] = []
    length = 0
    for index in ranked:
        if len(chosen) >= max_sentences:
            break
        sentence = sentences[index]
        if length + len(sentence) + 1 > max_chars and chosen:
            break
        chosen.append(index)
        length += len(sentence) + 1

    chosen.sort()
    text = re.sub(r"\s+", " ", " ".join(sentences[index] for index in chosen)).strip()
    return DocumentSummary(text=text, method="extractive")


def build_summary_prompt(document_name: str, parsed: ParsedDocument) -> str:
    body = "\n".join(page.text for page in parsed.pages if page.text)[:MAX_PROMPT_CHARS]
    return (
        "Summarize the following document in two or three sentences. "
        "Describe only what the document actually says; do not speculate or add outside context.\n\n"
        f"Title: {document_name}\n\nDocument:\n{body}\n\nSummary:"
    )


def clean_model_summary(raw: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    text = re.sub(r"\s+", " ", raw).strip()
    # Small local models often restate the instruction before answering.
    text = re.sub(r"^(summary|here is a summary|this document)\s*[:\-—]\s*", "", text, flags=re.IGNORECASE)
    if len(text) <= max_chars:
        return text
    # Prefer cutting at a sentence boundary over mid-word truncation.
    clipped = text[:max_chars]
    boundary = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    return clipped[: boundary + 1] if boundary > max_chars // 2 else clipped.rstrip() + "…"
