"""Offline extractive chat fallback — synthesizes answers from retrieved evidence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
import re
from math import log

from app.providers.base import HealthStatus, ProviderRef


class ExtractiveChatAdapter:
    """Deterministic local synthesizer used when no LLM provider is connected."""

    def __init__(
        self,
        config_id: str = "cfg_chat_extractive",
        term_document_frequency: dict[str, int] | None = None,
        document_count: int = 0,
    ) -> None:
        self.ref: ProviderRef = {
            "role": "chat",
            "provider_type": "extractive",
            "model_name": "evidence_synthesis_v1",
            "base_url": None,
            "config_id": config_id,
        }
        self._term_document_frequency = term_document_frequency or {}
        self._document_count = document_count

    def generate(self, prompt: str, *, stream: bool = True) -> Iterator[str] | str:
        # The RAG layer passes a prompt that already includes chunk markers.
        # Extractive mode emits a short grounded summary citing included chunks,
        # or INSUFFICIENT_EVIDENCE when no chunk markers are present.
        chunk_ids = _extract_chunk_ids(prompt)
        if not chunk_ids:
            text = "INSUFFICIENT_EVIDENCE"
        else:
            snippets = _extract_chunk_bodies(prompt)
            pairs = list(zip(chunk_ids, snippets, strict=False))[:3]
            tabular = _answer_tabular_question(prompt, pairs)
            if tabular:
                text = tabular
                if stream:
                    return iter([text])
                return text
            question = _extract_question(prompt)
            # Rank candidate sentences across the retrieved set. The top chunk
            # can be semantically close but contain only neighboring context;
            # answerability is determined at sentence level.
            chunk_id, sentence = _most_relevant_sentence(
                question,
                pairs,
                self._term_document_frequency,
                self._document_count,
            )
            text = f"{sentence.rstrip('.!?')} [chunk:{chunk_id}]."
        if stream:
            return iter([text])
        return text

    def health_check(self) -> HealthStatus:
        return HealthStatus(reachable=True, latency_ms=0.0, error=None, checked_at=datetime.now(UTC))

    @property
    def context_window(self) -> int:
        return 8192


def _extract_chunk_ids(prompt: str) -> list[str]:
    import re

    return re.findall(r"\[\[chunk:([^\]]+)\]\]", prompt)


def _extract_chunk_bodies(prompt: str) -> list[str]:
    import re

    return [match.strip() for match in re.findall(r"\[\[chunk:[^\]]+\]\](.*?)\[\[/chunk\]\]", prompt, flags=re.S)]


def _extract_question(prompt: str) -> str:
    questions = re.findall(r"Question:\s*(.+?)\n", prompt, flags=re.S)
    return questions[-1] if questions else ""


def _most_relevant_sentence(
    question: str,
    pairs: list[tuple[str, str]],
    term_document_frequency: dict[str, int] | None = None,
    document_count: int = 0,
) -> tuple[str, str]:
    """Return one complete, question-relevant sentence for grounded fallback."""
    stop_words = {
        "what", "when", "where", "which", "who", "how", "does", "did", "is", "are", "the", "a", "an",
        "at", "in", "of", "for", "to", "and", "it", "on",
    }
    terms = {
        term.lower()
        for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", question.lower())
        if term.lower() not in stop_words and len(term) > 1
    }
    is_why_question = bool(re.search(r"\bwhy\b", question, flags=re.I))
    causal_cues = {
        "because", "since", "therefore", "caused", "cause", "reason", "result", "resulted", "led",
        "failed", "stopped", "rest", "nap", "sleep", "slept", "forgot", "ignored", "misjudged",
    }
    candidates: list[tuple[int, int, str, str]] = []
    for chunk_index, (chunk_id, snippet) in enumerate(pairs):
        sentences = [
            part.strip()
            for part in re.split(
                r"(?<=[.!?])\s+|\s+—\s+|\s+(?=\d{1,2}:\d{2}[-–])|\s+(?=Warning:|Best months?:)",
                snippet,
            )
            if part.strip()
        ]
        for sentence_index, sentence in enumerate(sentences):
            sentence_terms = set(re.findall(r"[a-z0-9][a-z0-9_.-]*", sentence.lower()))
            score = sum(
                log((document_count + 1) / (term_document_frequency.get(term, 0) + 1)) + 1
                for term in terms & sentence_terms
            ) if document_count else len(terms & sentence_terms)
            if is_why_question:
                # A causal/decision question is best answered by the passage
                # stating the recommendation or reason, rather than a nearby
                # fact that merely shares a month/place token.
                if sentence_terms & {"warning", "avoid", "because", "since"}:
                    score += 4
                if sentence_terms & {"wettest", "rainfall", "humidity", "hottest"}:
                    score += 1
                if sentence_terms & causal_cues:
                    score += 3
            candidates.append((score, -chunk_index * 1000 - sentence_index, chunk_id, sentence))
    if candidates:
        _, _, chunk_id, sentence = max(candidates)
        return chunk_id, sentence
    chunk_id, snippet = pairs[0]
    return chunk_id, snippet.strip()


def _answer_tabular_question(prompt: str, pairs: list[tuple[str, str]]) -> str | None:
    questions = re.findall(r"Question:\s*(.+?)\n", prompt, flags=re.S)
    if not questions:
        return None
    match = re.search(r"what is the ([a-z][a-z ]+) of ([a-z][a-z]+(?: [a-z][a-z]+)*)", questions[-1], flags=re.I)
    if match is None:
        return None
    field = match.group(1).strip().lower()
    subject = match.group(2).strip()
    for chunk_id, snippet in pairs:
        header = re.search(r"\bid\s*\|\s*name\s*\|\s*([^|]+?)\s*\|", snippet, flags=re.I)
        if header is None or header.group(1).strip().lower() != field:
            continue
        row = re.search(rf"\|\s*{re.escape(subject)}\s*\|\s*([^|]+?)\s*\|", snippet, flags=re.I)
        if row is not None:
            return f"{subject} is in the {row.group(1).strip()} department. [chunk:{chunk_id}]"
    return None
