"""RAG grounding pipeline (docs/11_RAG_ARCHITECTURE.md)."""

from __future__ import annotations

import logging
import json
import os
import re
from math import log
from time import perf_counter
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations
from difflib import SequenceMatcher
from typing import Literal
from uuid import uuid4

from app.core.config import Settings
from app.domain.models import Citation, Evidence, GroundedResponse, SearchScope, utc_now
from app.providers.extractive import _matching_label_passages
from app.providers.registry import ProviderRegistry
from app.repositories import AnyRepository
from app.services.vector_store import RetrievedChunk, VectorStore, relevance_bucket
from app.services import structured
from app.services.page_queries import parse_page_reference

CITATION_RE = re.compile(r"\[chunk:([^\]]+)\]")
logger = logging.getLogger("duckdocs.rag")
logger.setLevel(getattr(logging, os.getenv("DUCKDOCS_LOG_LEVEL", "INFO").upper(), logging.INFO))
if os.getenv("DUCKDOCS_LOG_LEVEL", "INFO").upper() == "DEBUG" and not logger.handlers:
    _timing_handler = logging.StreamHandler()
    _timing_handler.setLevel(logging.DEBUG)
    logger.addHandler(_timing_handler)
    logger.propagate = False


def _generate_chat(chat: object, prompt: str) -> Iterator[str] | str:
    generate = getattr(chat, "generate")
    if getattr(chat, "ref", {}).get("provider_type") == "ollama":
        passage_numbers = [int(value) for value in re.findall(r"\[\[chunk:(\d+)\]\]", prompt)]
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "integer", "enum": passage_numbers},
                    "maxItems": len(passage_numbers),
                },
            },
            "required": ["answer", "evidence_ids"],
            "additionalProperties": False,
        }
        return generate(prompt, stream=False, structured_output=schema)
    return generate(prompt, stream=False)


def _log_stage(stage: str, started: float, **fields: object) -> None:
    logger.debug("ask_stage=%s duration_ms=%.1f %s", stage, (perf_counter() - started) * 1000, " ".join(
        f"{key}={value}" for key, value in fields.items()
    ))


def _split_terms(value: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_.-]*", value.lower()):
        terms.update(part for part in re.findall(r"[a-z0-9]+", token) if len(part) > 2)
    return terms


@dataclass(slots=True)
class GateResult:
    outcome: Literal["grounded", "insufficient_evidence"]
    text: str | None
    cited_ids: list[str]
    reason: str | None = None


@dataclass(slots=True)
class ConfidenceBreakdown:
    overall: float
    retrieval: float
    ocr: float
    coverage: float


class GroundingGate:
    def validate(
        self,
        raw_output: str,
        allowed_chunk_ids: set[str],
        task: str = "ask",
        evidence_by_id: dict[str, str] | None = None,
        query: str | None = None,
        evidence_metadata: dict[str, Evidence] | None = None,
        term_document_frequency: dict[str, int] | None = None,
        document_pages: dict[str, int] | None = None,
    ) -> GateResult:
        stripped = raw_output.strip()
        if stripped == "INSUFFICIENT_EVIDENCE" or stripped.startswith("INSUFFICIENT_EVIDENCE"):
            return GateResult(outcome="insufficient_evidence", text=None, cited_ids=[], reason="model_declined")

        if stripped.startswith("{") and not CITATION_RE.search(stripped):
            try:
                json.loads(stripped)
            except json.JSONDecodeError:
                return GateResult(outcome="insufficient_evidence", text=None, cited_ids=[], reason="invalid_json")

        structured = _parse_structured_claims(stripped)
        if structured is not None:
            verified: list[tuple[str, str]] = []
            for claim, evidence_id, quote in structured:
                if evidence_id not in allowed_chunk_ids or not evidence_by_id:
                    continue
                source = evidence_by_id.get(evidence_id, "")
                if _evidence_matches_query_hints(query, evidence_metadata, evidence_id, document_pages) and _quote_matches(quote, source):
                    verified.append((claim, evidence_id))
            if not verified:
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="no_evidence" if not structured else "claim_not_in_evidence",
                )
            normalized = " ".join(f"{claim.rstrip('.!?')} [chunk:{evidence_id}]." for claim, evidence_id in verified)
            return GateResult(
                outcome="grounded",
                text=normalized,
                cited_ids=list(dict.fromkeys(evidence_id for _, evidence_id in verified)),
            )

        simple = _parse_simple_answer(stripped)
        if simple is not None:
            answer, cited_ids = simple
            if any(cited_id not in allowed_chunk_ids for cited_id in cited_ids):
                return GateResult(outcome="insufficient_evidence", text=None, cited_ids=[], reason="unknown_evidence_id")
            if _answer_adds_no_information(answer, query):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="content_not_informative",
                )
            cited_ids = [
                evidence_id
                for evidence_id in cited_ids
                if _evidence_matches_query_hints(query, evidence_metadata, evidence_id, document_pages)
            ]
            if not cited_ids:
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="format_mismatch",
                )
            if (
                not answer
                or not cited_ids
                or any(cited_id not in allowed_chunk_ids for cited_id in cited_ids)
                or not evidence_by_id
                or any(not evidence_by_id.get(cited_id, "").strip() for cited_id in cited_ids)
                or _looks_like_junk_output(answer, query)
                or not _claims_match_evidence([answer], cited_ids, evidence_by_id)
            ):
                reason = "no_evidence"
                if not answer:
                    reason = "empty_answer"
                elif any(not evidence_by_id.get(cited_id, "").strip() for cited_id in cited_ids):
                    reason = "empty_evidence"
                elif _looks_like_junk_output(answer, query):
                    reason = "vacuous_answer"
                elif not _claims_match_evidence([answer], cited_ids, evidence_by_id):
                    reason = "claim_not_in_evidence"
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason=reason,
                )
            if _answer_type_missing(query, cited_ids, evidence_by_id, answer):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="answer_type_missing",
                )
            if _attribute_missing(query, cited_ids, evidence_by_id, term_document_frequency):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="attribute_missing",
                )
            normalized = f"{answer.rstrip('.!?')} [chunk:{cited_ids[0]}]."
            return GateResult(
                outcome="grounded",
                text=normalized,
                cited_ids=list(dict.fromkeys(cited_ids)),
            )

        if _looks_like_junk_output(stripped, query):
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="content_not_grounded",
            )

        cited_ids = CITATION_RE.findall(raw_output)
        canonical_ids: dict[str, str] = {}
        for cited_id in cited_ids:
            if cited_id in allowed_chunk_ids:
                canonical_ids[cited_id] = cited_id
                continue
            matches = sorted(
                allowed_id
                for allowed_id in allowed_chunk_ids
                if allowed_id.startswith(f"{cited_id}_")
                and allowed_id.removeprefix(f"{cited_id}_").isdigit()
            )
            if matches:
                canonical_ids[cited_id] = matches[0]

        unknown = set(cited_ids) - canonical_ids.keys()
        if unknown:
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="gate_rejected_output",
            )

        cited_ids = [canonical_ids[cited_id] for cited_id in cited_ids]
        cited_ids = [
            evidence_id
            for evidence_id in cited_ids
            if _evidence_matches_query_hints(query, evidence_metadata, evidence_id, document_pages)
        ]

        if task == "ask" and cited_ids:
            if _answer_type_missing(query, cited_ids, evidence_by_id, stripped):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=cited_ids,
                    reason="answer_type_missing",
                )
            if _attribute_missing(query, cited_ids, evidence_by_id, term_document_frequency):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=cited_ids,
                    reason="attribute_missing",
                )
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
            factual = [sentence for sentence in sentences if _looks_factual(sentence)]
            uncited = [
                sentence
                for index, sentence in enumerate(sentences)
                if _looks_factual(sentence)
                and not CITATION_RE.search(sentence)
                and not (
                    index + 1 < len(sentences)
                    and CITATION_RE.fullmatch(sentences[index + 1].strip(" ."))
                )
            ]
            structured_context = (
                evidence_metadata
                and any(
                    _is_structured_document(evidence_metadata.get(evidence_id))
                    for evidence_id in cited_ids
                )
                and (_looks_like_structured_answer(stripped) or _looks_like_key_value_answer(stripped))
            )
            if factual and len(uncited) / max(1, len(factual)) > 0.6 and not structured_context:
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=cited_ids,
                    reason="citation_density_low",
                )

            if evidence_by_id is not None and not _claims_match_evidence(sentences, cited_ids, evidence_by_id):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=cited_ids,
                    reason="content_not_grounded",
                )

        if not cited_ids and task == "ask":
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="citation_density_low",
            )

        if task == "ask" and not cited_ids:
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="no_evidence",
            )
        return GateResult(outcome="grounded", text=raw_output, cited_ids=list(dict.fromkeys(cited_ids)))


def _parse_structured_claims(raw_output: str) -> list[tuple[str, str, str]] | None:
    if not raw_output.startswith("{"):
        return None
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        # Extractive answers may quote source JSON followed by an app citation.
        # They still need the ordinary claim, format, and citation checks.
        return None if CITATION_RE.search(raw_output) else []
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if claims is None:
        return None
    if not isinstance(claims, list):
        return []
    parsed: list[tuple[str, str, str]] = []
    for item in claims:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim") or item.get("text")
        evidence_id = item.get("evidence_id") or item.get("evidence")
        quote = item.get("quote")
        if all(isinstance(value, str) and value.strip() for value in (claim, evidence_id, quote)):
            parsed.append((claim.strip(), evidence_id.strip(), quote.strip()))
    return parsed


def _parse_simple_answer(raw_output: str) -> tuple[str, list[str]] | None:
    if not raw_output.startswith("{"):
        return None
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
        return None
    evidence_ids = payload.get("evidence_ids")
    if not isinstance(evidence_ids, list):
        return None
    normalized_ids = [str(value).strip() for value in evidence_ids if isinstance(value, (int, str))]
    return payload["answer"].strip(), [value for value in normalized_ids if value]


def _evidence_matches_query_hints(
    query: str | None,
    evidence_metadata: dict[str, Evidence] | None,
    evidence_id: str,
    document_pages: dict[str, int] | None = None,
) -> bool:
    if not query or not evidence_metadata:
        return True
    evidence = evidence_metadata.get(evidence_id)
    if evidence is None:
        return True
    lowered = query.lower()
    name = evidence.document_name.lower()
    extension = evidence.file_type or (name.rsplit(".", 1)[-1] if "." in name else "")
    expected = _query_format_extensions(lowered, {extension})
    if expected and extension not in expected:
        return False
    if "native text pdf" in lowered and (extension != "pdf" or evidence.fidelity_tier == "ocr_dependent"):
        return False
    if "scanned" in lowered and evidence.ocr_confidence is None:
        return False
    reference = parse_page_reference(query)
    if reference and not reference.matches(evidence.page, extension, (document_pages or {}).get(evidence.document_id)):
        return False
    return True


def _query_format_extensions(query: str, available: set[str]) -> set[str]:
    """Resolve format words to extensions that are actually present."""
    if re.search(r"\b(?:excel|xlsx)\b", query):
        return {"xlsx"}
    if re.search(r"\bcsv\b", query):
        return {"csv"}
    explicit_keys = set().union(*(extensions for phrase, extensions in {
        "yaml": {"yaml", "yml"}, "yml": {"yaml", "yml"}, "json": {"json"}, "xml": {"xml"}
    }.items() if re.search(rf"\b{phrase}\b", query)))
    if explicit_keys:
        return explicit_keys & available or explicit_keys
    groups = {
        "pdf": {"pdf"},
        "docx": {"docx", "doc"},
        "word": {"docx", "doc"},
        "spreadsheet": {"xlsx", "xls", "csv"},
        "yaml": {"yaml", "yml"},
        "json": {"json"},
        "xml": {"xml"},
        "html": {"html", "htm"},
        "markdown": {"md", "markdown"},
        "notes": {"md", "markdown", "txt"},
        "web page": {"html", "htm"},
        "config": {"yaml", "yml", "json", "xml"},
        "presentation": {"pptx", "ppt"},
        "slides": {"pptx", "ppt"},
        "image": {"png", "jpg", "jpeg", "gif", "webp"},
        "picture": {"png", "jpg", "jpeg", "gif", "webp"},
        "photo": {"png", "jpg", "jpeg", "gif", "webp"},
    }
    requested = set().union(*(extensions for phrase, extensions in groups.items() if phrase in query))
    if re.search(r"\bsheets?\b", query):
        requested.update({"xlsx", "xls", "csv"})
    present = requested & available
    return present if present else requested


def _quote_matches(quote: str, source: str) -> bool:
    normalized_quote = " ".join(quote.lower().split())
    normalized_source = " ".join(source.lower().split())
    if not normalized_quote or not normalized_source:
        return False
    if normalized_quote in normalized_source:
        return True
    return SequenceMatcher(None, normalized_quote, normalized_source).ratio() >= 0.9


def _answer_type_missing(
    query: str | None,
    cited_ids: list[str],
    evidence_by_id: dict[str, str] | None,
    answer: str | None = None,
) -> bool:
    if not query or not evidence_by_id:
        return False
    lowered = query.lower()
    asks_numeric = bool(
        re.search(r"\b(?:how much|how many|prices?|pricing|costs?|fees?|charges?|fares?|tariffs?|amount|rate|count)\b", lowered)
    )
    currency_word = re.search(r"\b(?:usd|eur|gbp|inr|jpy|cad|aud|dollars?|euros?|pounds?|rupees?|yen|currency)\b|[$€£₹]", lowered)
    if currency_word and re.search(r"\b(?:pay|pays|paid|payment|payments|spend|spent|budget|expenses?|worth|priced)\b", lowered):
        asks_numeric = True
    asks_date = bool(re.search(r"\bwhen\b", lowered))
    if not asks_numeric and not asks_date:
        return False
    sources = [evidence_by_id.get(evidence_id, "") for evidence_id in cited_ids]
    if answer is not None:
        sources = [select_evidence_passage(query, answer, source) for source in sources]
    source = " ".join(sources)
    if asks_date and re.search(
        r"\b(?:19|20)\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
        source,
        flags=re.I,
    ):
        return False
    if asks_numeric and re.search(r"\b\d+(?:[.,]\d+)*\b|[$€£₹]\s?\d|\b\d+\s?%|\b(?:USD|EUR|GBP|INR|JPY|CAD|AUD|Rs\.?)\s*\d", source, flags=re.I):
        return False
    return True


def _attribute_missing(
    query: str | None,
    cited_ids: list[str],
    evidence_by_id: dict[str, str] | None,
    term_document_frequency: dict[str, int] | None,
) -> bool:
    if not query or not evidence_by_id or not term_document_frequency:
        return False
    if not re.search(r"\bwhat is\b|\bwhich\b", query, flags=re.I):
        return False
    if re.search(r"\b(?:total|sum|average|across|between)\b", query, flags=re.I):
        return False
    query_terms = _split_terms(query)
    source_text = " ".join(evidence_by_id.get(evidence_id, "") for evidence_id in cited_ids)
    source_terms = _split_terms(source_text)
    capitalized_terms = _split_terms(" ".join(re.findall(r"\b[A-Z][a-z0-9_.-]*\b", query)))
    rare_entity_terms = {
        term for term in query_terms
        if term in capitalized_terms and term_document_frequency.get(term, 0) <= 1
    }
    attribute_terms = query_terms - rare_entity_terms
    attribute_terms -= _DOCUMENT_DESCRIPTOR_TERMS
    attribute_terms -= _GROUNDING_STOP_WORDS
    if not rare_entity_terms or not attribute_terms:
        return False
    stemmed_source = {_stem(term) for term in source_terms}
    if any(_stem(term) in stemmed_source for term in attribute_terms):
        return False
    compact_source = re.sub(r"[^a-z0-9]+", "", source_text.lower())
    compact_attribute = "".join(
        term
        for term in re.findall(r"[a-z0-9]+", query.lower())
        if term in attribute_terms
    )
    return not compact_attribute or compact_attribute not in compact_source


def _stem(term: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(term) > len(suffix) + 3 and term.endswith(suffix):
            return term[: -len(suffix)]
    return term


def _looks_like_junk_output(output: str, query: str | None) -> bool:
    clean = CITATION_RE.sub("", output).strip(" \t\r\n.")
    if re.search(r"^(?:question|answer|context):", clean, flags=re.IGNORECASE | re.MULTILINE):
        return True
    if query and " ".join(clean.lower().split()) == " ".join(query.lower().split()):
        return True
    if re.match(r"^(?:i am|i found|i can|i will|as an ai|based on the evidence|the answer is)", clean, flags=re.I):
        return True
    if re.fullmatch(r"the record identifies the .+ department", clean, flags=re.I):
        return True
    return False


def _answer_adds_no_information(answer: str, query: str | None) -> bool:
    if not query:
        return False

    def normalized_terms(value: str) -> set[str]:
        ordinal_numbers = {
            "first": "1", "second": "2", "third": "3", "fourth": "4",
            "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8",
            "ninth": "9", "tenth": "10",
        }
        terms = set(re.findall(r"[a-z0-9]+", value.lower()))
        return {
            ordinal_numbers.get(term, term) for term in terms
            if term not in _GROUNDING_STOP_WORDS | _DOCUMENT_DESCRIPTOR_TERMS
        }

    answer_terms = normalized_terms(answer)
    query_terms = normalized_terms(query)
    return not answer_terms or answer_terms <= query_terms


def _is_structured_document(evidence: Evidence | None) -> bool:
    if evidence is None:
        return False
    return (getattr(evidence, "file_type", None) or evidence.document_name.rsplit(".", 1)[-1].lower()) in {"xml", "yaml", "yml", "json", "csv"}


def _looks_like_structured_answer(value: str) -> bool:
    return bool(re.search(r"<[a-z][^>]*>|[a-z][\w.-]*\s*:\s*[^:\n]+|\|[^|]+\|", value, re.I))


def _looks_like_key_value_answer(value: str) -> bool:
    return bool(re.search(r"\b(?:is|are|equals?)\s+\S+", value, re.I))


def _claims_match_evidence(
    sentences: list[str], cited_ids: list[str], evidence_by_id: dict[str, str]
) -> bool:
    evidence = " ".join(evidence_by_id.get(evidence_id, "") for evidence_id in set(cited_ids)).lower()
    evidence_terms = set(re.findall(r"[a-z0-9]+(?:[_.-][a-z0-9]+)*", evidence))
    evidence_numbers = [int(value.replace(",", "")) for value in re.findall(r"\b\d[\d,]*\b", evidence)]
    factual = [sentence for sentence in sentences if _looks_factual(sentence)]
    for sentence in factual:
        # Citation IDs identify the supporting chunk; they are metadata, not
        # claim text, and must not be compared against the evidence vocabulary.
        claim = CITATION_RE.sub("", sentence)
        terms = [
            term
            for term in re.findall(r"[a-z0-9]+(?:[_.-][a-z0-9]+)*", claim.lower())
            if term not in _GROUNDING_STOP_WORDS and len(term) > 2
        ]
        supported = {term for term in terms if term in evidence_terms}
        missing = set(terms) - supported
        claim_numbers = [int(value.replace(",", "")) for value in re.findall(r"\b\d[\d,]*\b", claim)]
        # `evidence_numbers` already removes thousands separators; comparing
        # against raw token strings incorrectly rejects supported values like
        # 2,000 (whose normalized claim token is 2000).
        missing_numbers = [number for number in claim_numbers if number not in evidence_numbers]
        if missing_numbers and not all(_is_derived_number(number, evidence_numbers) for number in missing_numbers):
            return False
        if missing - {"units", "unit", "stock", "total", "sum"} and len(missing - {"units", "unit", "stock", "total", "sum"}) > 1:
            return False
    return True


def _is_derived_number(target: int, source_numbers: list[int]) -> bool:
    for size in range(2, min(4, len(source_numbers) + 1)):
        if any(sum(values) == target for values in combinations(source_numbers, size)):
            return True
    return False


def select_evidence_passage(query: str, answer: str, snippet: str) -> str:
    """Return the smallest source sentence/clause that covers the answer's key terms.

    Chunk IDs and source metadata remain attached to the citation; this only
    narrows the quoted text used by the evidence panel.
    """
    clean_answer = CITATION_RE.sub("", answer)

    def tokenize(value: str) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9]+(?:[_.-][a-z0-9]+)*", value.lower()))
        for token in tuple(tokens):
            tokens.update(part for part in re.split(r"[_.-]", token) if len(part) > 2)
        ordinals = {
            "first": "1", "second": "2", "third": "3", "fourth": "4",
            "fifth": "5", "sixth": "6", "seventh": "7",
        }
        tokens.update(ordinals[token] for token in tuple(tokens) if token in ordinals)
        return tokens

    answer_terms = {
        term for term in tokenize(clean_answer) if term not in _EVIDENCE_STOP_WORDS and len(term) > 2
    }
    query_terms = {
        term for term in tokenize(query) if term not in _EVIDENCE_STOP_WORDS and len(term) > 2
    }
    query_terms -= _DOCUMENT_DESCRIPTOR_TERMS
    if not answer_terms:
        return ""

    label_passages = [
        passage for passage in _matching_label_passages(query, snippet)
        if len(tokenize(passage) & answer_terms) >= max(1, len(answer_terms) - 1)
    ]
    if label_passages:
        snippet = "\n".join(label_passages)

    # Split at sentence and phrase boundaries. PDF extraction can flatten
    # headings into sentences, so commas and dashes also define candidate spans.
    candidates: list[tuple[str, set[str]]] = []
    sentence_parts = re.split(
        r"(?<=[.!?])\s+|\n+|\s+(?=(?:The|Warning:|Avoid)\b)", snippet
    )
    for sentence in sentence_parts:
        for match in re.finditer(r"[^,;\u2014\u2013]+", sentence):
            start = match.start()
            if start and sentence[start - 1] in "\u2014\u2013":
                start -= 1
            passage = sentence[start:match.end()].strip()
            if passage:
                candidates.append((passage, tokenize(passage)))
    if not candidates:
        return ""

    source_terms = set().union(*(terms for _, terms in candidates))
    original_query_terms = set(query_terms)
    query_terms &= source_terms
    # Keep the citation tied to the subject asked about. If the retrieved
    # chunk does not contain any non-generic query term, it cannot support a
    # passage for this answer even if unrelated answer words happen to match.
    if query_terms and not (query_terms & answer_terms):
        return ""
    if not query_terms and original_query_terms and not (answer_terms & original_query_terms):
        return ""
    if not query_terms and not original_query_terms and not (answer_terms & source_terms):
        return ""
    # In a relevant restaurant row, "Order ..." is the recommendation verb
    # even when the generated answer names only the venue. Do not use this
    # generic term to make an unrelated restaurant row appear relevant.
    if "restaurant" in query.lower():
        query_terms.add("order")

    # A person/place name can repeat throughout a chunk. Discount terms shared
    # by most candidate spans so they do not pull neighboring sentences in.
    common_terms = {
        term for term in answer_terms
        if len(candidates) >= 3 and sum(term in terms for _, terms in candidates) > len(candidates) / 2
    }
    answer_terms -= common_terms
    candidates = [(text, terms) for text, terms in candidates]

    answer_overlap = [len(terms & answer_terms) for _, terms in candidates]
    label_question = bool(re.search(r"\bwhat is the\b", query, flags=re.I))
    label_value = [
        1 if label_question and overlap and re.search(r"[\w.-]+\s*:\s*\S+", text) else 0
        for (text, _), overlap in zip(candidates, answer_overlap, strict=True)
    ]
    answer_overlap = [
        overlap + (2 if label_value[index] else 0)
        for index, overlap in enumerate(answer_overlap)
    ]
    best_answer_overlap = max(answer_overlap, default=0)
    if best_answer_overlap == 0:
        query_overlap = [len(terms & query_terms) for _, terms in candidates]
        best_query_overlap = max(query_overlap, default=0)
        if best_query_overlap == 0:
            return ""
        selected = [
            text.rstrip(".!? ")
            for (text, _), overlap in zip(candidates, query_overlap, strict=True)
            if overlap == best_query_overlap
        ]
        result = " ".join(dict.fromkeys(selected))
        if "\n" in snippet and result:
            lines = [line.strip() for line in snippet.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                if result in line and index > 0:
                    heading = lines[index - 1]
                    if len(heading.split()) <= 8 and not re.search(r"[.!?]$", heading):
                        heading_terms = tokenize(heading)
                        if heading_terms & answer_terms:
                            result = f"{heading} {result}"
                    break
        return result
    answer_overlap_required = max(1, min(2, best_answer_overlap - 1))
    selected = [
        text.rstrip(".!? ") for (text, terms), overlap in zip(candidates, answer_overlap, strict=True)
        if overlap >= answer_overlap_required
        or ("restaurant" in query.lower() and "order" in terms and bool(terms & query_terms))
    ]
    return " ".join(dict.fromkeys(selected))


_GROUNDING_STOP_WORDS = {
    "the", "and", "are", "from", "into", "with", "that", "this", "was", "were", "has", "have",
    "based", "retrieved", "evidence", "record", "records", "answer", "indicates", "shows", "is", "in",
    "of", "to", "for", "on", "as", "an", "a", "be", "by", "or", "its", "their", "there", "it",
    "what", "which", "how", "does", "do", "all", "total", "value", "values", "across", "row", "rows",
}

_EVIDENCE_STOP_WORDS = _GROUNDING_STOP_WORDS | {
    "according", "document", "please", "tell", "explain", "why", "when", "where", "who",
    "visit", "visiting", "recommended", "recommend", "answer", "provide", "based",
    "restaurant", "restaurants", "food", "avoid",
    "he", "him", "his", "she", "her", "they", "them",
}

_RETRIEVAL_SUPPORT_STOP_WORDS = _GROUNDING_STOP_WORDS | {
    "according", "document", "recommend", "recommended",
}

_DOCUMENT_DESCRIPTOR_TERMS = {
    "file", "document", "page", "slide", "sheet", "pdf", "text", "test",
    "yaml", "yml", "xml", "json", "csv", "html", "markdown", "md",
    "native", "scanned", "ocr", "spreadsheet", "presentation", "word",
}


def _looks_factual(sentence: str) -> bool:
    lowered = sentence.lower().strip()
    if CITATION_RE.search(sentence):
        return True
    if lowered.startswith(
        (
            "in summary",
            "overall",
            "therefore",
            "thus",
            "based on the retrieved",
            "i found the strongest",
            "the answer is supported",
        )
    ):
        return False
    if CITATION_RE.fullmatch(lowered.strip(" .")):
        return False
    return any(char.isdigit() for char in sentence) or len(sentence.split()) > 3


def build_ask_prompt(
    query: str,
    chunks: list[RetrievedChunk],
    *,
    max_chunks: int = 6,
    max_chars: int = 1200,
    context_window: int = 4096,
) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks[:max_chunks], start=1):
        snippet = chunk.evidence.snippet[:max_chars]
        blocks.append(
            f"[[chunk:{index}]]\n{snippet}\n[[/chunk]]"
        )
    context = "\n\n".join(blocks)
    prompt = (
        "Answer only from the provided context.\n"
        "Return a JSON object with a short answer and an evidence_ids array. "
        "Use the passage numbers as evidence_ids. Do not copy quotes.\n"
        "If the context is insufficient, return {\"answer\":\"\",\"evidence_ids\":[]}.\n\n"
        f"Question: {query}\n\nContext:\n{context}\n\nAnswer:"
    )
    estimated_tokens = (len(prompt) + 3) // 4
    logger.debug(
        "ask_prompt chars=%d estimated_tokens=%d context_window=%d chunks=%d",
        len(prompt),
        estimated_tokens,
        context_window,
        min(len(chunks), max_chunks),
    )
    return prompt


def score_confidence(chunks: list[RetrievedChunk], cited_ids: list[str]) -> ConfidenceBreakdown:
    cited = [chunk for chunk in chunks if chunk.evidence.id in cited_ids]
    retrieval = sum(chunk.score for chunk in cited) / max(1, len(cited)) if cited else 0.0
    # A hardcoded 1.0 here would systematically overstate confidence for every
    # answer grounded in a scanned document -- exactly the number RULE-10 says
    # must reflect real uncertainty. Average the real OCR confidence of cited
    # chunks that have one; a citation with no OCR confidence contributes
    # nothing to discount because it wasn't recognized, it was extracted.
    ocr_values = [chunk.evidence.ocr_confidence for chunk in cited if chunk.evidence.ocr_confidence is not None]
    ocr = sum(ocr_values) / len(ocr_values) if ocr_values else 1.0
    coverage = len(set(cited_ids)) / max(1, len(chunks))
    overall = 0.5 * retrieval + 0.3 * ocr + 0.2 * coverage
    return ConfidenceBreakdown(
        overall=round(overall, 3), retrieval=round(retrieval, 3), ocr=round(ocr, 3), coverage=round(coverage, 3)
    )


class RagService:
    def __init__(
        self,
        settings: Settings,
        repository: AnyRepository,
        registry: ProviderRegistry,
        vector_store: VectorStore,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.registry = registry
        self.vector_store = vector_store
        self.gate = GroundingGate()

    def retrieve(self, query: str, scope: SearchScope | None = None) -> list[RetrievedChunk]:
        document_ids: list[str] | None = None
        if scope and scope.type == "document" and scope.document_id:
            document_ids = [scope.document_id]
        elif scope and scope.type == "selection" and scope.document_ids:
            document_ids = list(scope.document_ids)

        candidate_ids = self._hint_candidate_ids(query, document_ids)
        if candidate_ids == set():
            return []
        candidate_document_ids = (
            sorted({self.repository.evidence[evidence_id].document_id for evidence_id in candidate_ids})
            if candidate_ids is not None
            else document_ids
        )
        embedder = self.registry.get_embedding_provider()
        page_constraints = ({self.repository.evidence[key].document_id: self.repository.evidence[key].page
                             for key in candidate_ids} if parse_page_reference(query) and candidate_ids is not None else None)
        vector_hits = self.vector_store.query(
            query,
            embedder,
            self.repository.evidence,
            top_k=self.settings.top_k,
            min_similarity=self.settings.min_similarity,
            document_ids=candidate_document_ids,
            page_constraints=page_constraints,
        )
        if page_constraints is not None and candidate_ids is not None:
            vector_hits = [chunk for chunk in vector_hits if chunk.evidence.id in candidate_ids]
        keyword_hits = self.repository.search_evidence(query, max(self.settings.top_k, len(self.repository.evidence)))
        if candidate_ids is not None:
            keyword_hits = [item for item in keyword_hits if item.id in candidate_ids]
        elif document_ids:
            keyword_hits = [item for item in keyword_hits if item.document_id in document_ids]
        term_document_frequency, document_count = self._idf_stats()
        keyword_chunks = [
            self._keyword_chunk(query, item, term_document_frequency, document_count)
            for item in keyword_hits
            if self._has_lexical_support(query, item.snippet, item.document_name)
        ]
        keyword_cosines = self.vector_store.cosine_similarities(
            query,
            [chunk.evidence for chunk in keyword_chunks],
            embedder,
        )
        keyword_chunks = [
            RetrievedChunk(
                evidence=chunk.evidence,
                score=chunk.score,
                raw_cosine=keyword_cosines.get(chunk.evidence.id, 0.0),
                lexical_coverage=chunk.lexical_coverage,
            )
            for chunk in keyword_chunks
        ]
        vector_hits = [
            RetrievedChunk(
                evidence=chunk.evidence,
                score=chunk.score,
                raw_cosine=chunk.raw_cosine,
                lexical_coverage=self._keyword_chunk(
                    query, chunk.evidence, term_document_frequency, document_count
                ).lexical_coverage,
            )
            for chunk in vector_hits
        ]
        vector_rank = {chunk.evidence.id: rank for rank, chunk in enumerate(vector_hits, start=1)}
        keyword_rank = {chunk.evidence.id: rank for rank, chunk in enumerate(keyword_chunks, start=1)}
        by_id = {chunk.evidence.id: chunk for chunk in vector_hits}
        by_id.update({chunk.evidence.id: chunk for chunk in keyword_chunks})
        rrf_k = 60.0
        max_rrf = 1.0 / (rrf_k + 1)
        ranked: list[RetrievedChunk] = []
        for evidence_id, chunk in by_id.items():
            fused = sum(
                1.0 / (rrf_k + rank)
                for rank in (vector_rank.get(evidence_id), keyword_rank.get(evidence_id))
                if rank is not None
            )
            hint_boost = self._query_hint_boost(query, chunk.evidence)
            score = min(1.0, (fused / max_rrf) * hint_boost)
            ranked.append(
                RetrievedChunk(
                    evidence=chunk.evidence.model_copy(
                        update={"retrieval_score": score, "relevance": relevance_bucket(score, self.settings)}
                    ),
                    score=score,
                    raw_cosine=chunk.raw_cosine,
                    lexical_coverage=chunk.lexical_coverage,
                )
            )
        result = self._dedupe_chunks(sorted(
            ranked,
            key=lambda item: (
                self._spreadsheet_preference(query, item.evidence),
                item.score,
                item.raw_cosine + item.lexical_coverage + self._document_name_boost(query, item.evidence),
            ),
            reverse=True,
        )[: self.settings.top_k])
        if self.settings.reranker == "lexical":
            result.sort(key=lambda item: (self._keyword_chunk(query, item.evidence).score, item.score), reverse=True)
        logger.debug(
            "retrieval_top5=%s",
            [
                (
                    chunk.evidence.document_name,
                    round(chunk.score, 4),
                    round(chunk.raw_cosine, 4),
                    round(chunk.lexical_coverage, 4),
                )
                for chunk in result[:5]
            ],
        )
        return result

    def _idf_stats(self) -> tuple[dict[str, int], int]:
        document_terms: dict[str, set[str]] = {}
        for evidence in self.repository.evidence.values():
            document_terms.setdefault(evidence.document_id, set()).update(
                _split_terms(f"{evidence.document_name} {evidence.snippet}")
            )
        frequencies: dict[str, int] = {}
        for terms in document_terms.values():
            for term in terms:
                frequencies[term] = frequencies.get(term, 0) + 1
        return frequencies, len(document_terms)

    @staticmethod
    def _retrieval_signals(chunks: list[RetrievedChunk]) -> dict[str, float]:
        if not chunks:
            return {"top_raw_cosine": 0.0, "top_lexical_coverage": 0.0}
        return {
            "top_raw_cosine": round(chunks[0].raw_cosine, 4),
            "top_lexical_coverage": round(chunks[0].lexical_coverage, 4),
        }

    @staticmethod
    def _retrieval_top5(chunks: list[RetrievedChunk]) -> list[dict[str, str | float]]:
        return [
            {
                "document": chunk.evidence.document_name,
                "score": round(chunk.score, 4),
                "raw_cosine": round(chunk.raw_cosine, 4),
                "lexical_coverage": round(chunk.lexical_coverage, 4),
            }
            for chunk in chunks[:5]
        ]

    @staticmethod
    def _spreadsheet_preference(query: str, evidence: Evidence) -> int:
        generic = re.search(r"\b(?:spreadsheets?|sheets?)\b", query, flags=re.I)
        explicit_csv = re.search(r"\bcsv\b", query, flags=re.I)
        return int(bool(generic and not explicit_csv and (evidence.file_type or evidence.document_name.lower().rsplit(".", 1)[-1]) == "xlsx"))

    @staticmethod
    def _document_name_boost(query: str, evidence: Evidence) -> float:
        query_terms = _split_terms(query)
        name_terms = _split_terms(evidence.document_name)
        return 0.1 * len(query_terms & name_terms)

    def _hint_candidate_ids(
        self, query: str, document_ids: list[str] | None
    ) -> set[str] | None:
        candidates = {
            evidence.id
            for evidence in self.repository.evidence.values()
            if (document_ids is None or evidence.document_id in document_ids) and self._structured_source_ready(evidence)
        }
        if parse_page_reference(query):
            named = {e.document_id for e in self.repository.evidence.values() if e.id in candidates and re.search(
                rf"(?<!\w){re.escape(e.document_name)}(?!\w)", query, re.I)}
            if named:
                candidates = {key for key in candidates if self.repository.evidence[key].document_id in named}
        totals = self._document_pages()
        hinted = {
            evidence.id
            for evidence in self.repository.evidence.values()
            if evidence.id in candidates and self._matches_candidate_hints(query, evidence, candidates, totals)
        }
        return hinted

    def _matches_candidate_hints(self, query: str, evidence: Evidence, candidate_ids: set[str],
                                 document_pages: dict[str, int] | None = None) -> bool:
        lowered = query.lower()
        extension = evidence.file_type or evidence.document_name.lower().rsplit(".", 1)[-1]
        reference = parse_page_reference(query)
        if reference and not reference.matches(evidence.page, extension, (document_pages if document_pages is not None else self._document_pages()).get(evidence.document_id)):
            return False
        if ((re.search(r"\b(?:excel|xlsx)\b", lowered) and extension != "xlsx")
            or (re.search(r"\bcsv\b", lowered) and not re.search(r"[\w-]+\.csv\b", lowered) and extension != "csv")):
            return False
        if re.search(rf"(?<!\w){re.escape(evidence.document_name)}(?!\w)", query, flags=re.I):
            return True
        if "native text pdf" in lowered and (extension != "pdf" or evidence.fidelity_tier == "ocr_dependent"):
            return False
        if "scanned" in lowered and evidence.fidelity_tier != "ocr_dependent":
            return False
        available = {
            item.file_type or item.document_name.lower().rsplit(".", 1)[-1]
            for item in self.repository.evidence.values()
            if item.id in candidate_ids
        }
        expected = _query_format_extensions(lowered, available)
        explicit_excel = re.search(r"\b(?:excel|xlsx)\b", lowered)
        if expected and extension not in expected and (explicit_excel or not re.search(r"\b[\w-]+\.[a-z0-9]{2,5}\b", lowered)):
            return False
        return True

    def _document_pages(self) -> dict[str, int]:
        totals = {doc.id: doc.pages for doc in self.repository.documents.values()}
        for evidence in self.repository.evidence.values():
            if evidence.document_id not in self.repository.documents:
                totals[evidence.document_id] = max(totals.get(evidence.document_id, 0), evidence.page)
        return totals

    @staticmethod
    def _query_hint_boost(query: str, evidence: Evidence) -> float:
        lowered = query.lower()
        name = evidence.document_name.lower()
        boost = 1.0
        if "native text" in lowered and "native" in name:
            boost += 0.2
        if "scanned" in lowered and "scanned" in name:
            boost += 0.1
        if "ocr" in lowered and "ocr" in name:
            boost += 0.1
        if "multi-page" in lowered and "multipage" in name:
            boost += 0.1
        for extension, words in {
            "pdf": ("pdf",),
            "docx": ("word document",),
            "xlsx": ("spreadsheet",),
            "csv": ("spreadsheet", "csv"),
            "pptx": ("presentation",),
            "yaml": ("yaml",),
            "yml": ("yaml",),
            "xml": ("xml",),
        }.items():
            if any(word in lowered for word in words) and name.endswith(f".{extension}"):
                boost += 0.15
        reference = parse_page_reference(query)
        if reference and reference.matches(evidence.page, evidence.file_type or name.rsplit(".", 1)[-1]):
            boost += 0.25
        return boost

    def _prioritize_hint_chunks(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        totals = self._document_pages()
        hinted = [chunk for chunk in chunks if _evidence_matches_query_hints(query, {chunk.evidence.id: chunk.evidence}, chunk.evidence.id, totals)]
        if not hinted or len(hinted) == len(chunks):
            return chunks
        hinted_ids = {chunk.evidence.id for chunk in hinted}
        return hinted + [chunk for chunk in chunks if chunk.evidence.id not in hinted_ids]

    @staticmethod
    def _has_lexical_support(query: str, snippet: str, document_name: str = "") -> bool:
        query_terms = _split_terms(query) - _RETRIEVAL_SUPPORT_STOP_WORDS
        if not query_terms:
            return False
        snippet_terms = _split_terms(f"{document_name} {snippet}")
        matches = sum(term in snippet_terms for term in query_terms)
        if document_name and re.search(rf"(?<!\w){re.escape(document_name)}(?!\w)", query, flags=re.I):
            return True
        return matches >= (1 if len(query_terms) == 1 else 2)

    def _keyword_chunk(
        self,
        query: str,
        evidence: Evidence,
        term_document_frequency: dict[str, int] | None = None,
        document_count: int = 0,
    ) -> RetrievedChunk:
        terms = _split_terms(query)
        haystack = f"{evidence.document_name} {evidence.section} {evidence.snippet}".lower()
        matched = _split_terms(haystack)
        if term_document_frequency and document_count:
            weights = {
                term: max(0.0, log((document_count + 1) / (term_document_frequency.get(term, 0) + 1)))
                for term in terms
            }
            total_weight = sum(weights.values())
            score = sum(weights[term] for term in terms if term in matched) / max(total_weight, 1e-9)
        else:
            score = len(terms & matched) / max(1, len(terms))
        return RetrievedChunk(
            evidence=evidence.model_copy(
                update={
                    "retrieval_score": score,
                    "relevance": relevance_bucket(score, self.settings),
                }
            ),
            score=score,
            lexical_coverage=score,
        )

    @staticmethod
    def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen: set[tuple[str, int, int | None, str]] = set()
        unique: list[RetrievedChunk] = []
        for chunk in chunks:
            text = " ".join(chunk.evidence.snippet.lower().split())[:240]
            key = (chunk.evidence.document_id, chunk.evidence.page, chunk.evidence.paragraph_number, text)
            if not text or key in seen:
                continue
            seen.add(key)
            unique.append(chunk)
        return unique

    def index_document(self, document_id: str) -> int:
        units = [unit for unit in self.repository.evidence.values() if unit.document_id == document_id]
        if not units:
            return 0
        embedder = self.registry.get_embedding_provider()
        indexed_count = self.vector_store.upsert_evidence(units, embedder)
        if indexed_count != len(units):
            logger.error(
                "Vector indexing incomplete; existing vectors retained (document=%s expected=%d indexed=%d)",
                document_id,
                len(units),
                indexed_count,
            )
            return indexed_count
        # Upsert first, then remove obsolete chunk IDs. A transient embedding
        # or Chroma error must never erase a previously working index.
        self.vector_store.delete_document(document_id, keep_ids={unit.id for unit in units})
        return indexed_count

    def _structured_source_ready(self, evidence: Evidence) -> bool:
        document = self.repository.documents.get(evidence.document_id)
        return not (evidence.table_row or evidence.key_value) or document is None or document.status == "ready"

    def _structured_candidates(self, query: str, scope: SearchScope | None) -> tuple[list[Evidence], bool]:
        all_units = [e for e in self.repository.all_evidence() if self._structured_source_ready(e)]
        if scope and scope.type == "document":
            all_units = [e for e in all_units if e.document_id == scope.document_id]
        elif scope and scope.type == "selection":
            all_units = [e for e in all_units if e.document_id in (scope.document_ids or [])]
        named = {e.document_id for e in all_units if re.search(
            rf"(?<!\w){re.escape(e.document_name)}(?!\w)", query, re.I)}
        if named:
            all_units = [e for e in all_units if e.document_id in named]
        ids = {e.id for e in all_units}
        totals = self._document_pages()
        return [e for e in all_units if self._matches_candidate_hints(query, e, ids, totals)], bool(named)

    def _ask_table(self, query: str, scope: SearchScope | None) -> GroundedResponse | None:
        eligible, named = self._structured_candidates(query, scope)
        tables: dict[tuple[str, int], list[Evidence]] = {}
        for unit in eligible:
            if unit.table_row:
                tables.setdefault((unit.document_id, unit.page), []).append(unit.model_copy(deep=True))
        explicit = bool(re.search(r"\b(?:csv|xlsx|excel|spreadsheet|table)\b", query, re.I) or named
                        or (scope and scope.type == "document"))
        def supported(units: list[Evidence]) -> bool:
            try:
                effective = structured.table_query(query, units[0])
                return (bool(structured.mapped_columns(units[0].table_row.headers, effective))
                        or structured.requested_operation(effective, units[0].table_row.headers,
                                                          [u for u in units if not u.table_row.is_header]) == "count")
            except structured.StructuredError as error:
                return (error.code == "ambiguous_column"
                        or (error.code == "column_unmapped" and structured.table_entity_mentioned(units, query)))
        if not tables or (not explicit and not any(supported(units) for units in tables.values())):
            return None
        response = dict(id=f"resp_{uuid4().hex[:12]}", kind="ask", query=query,
                        created_at=utc_now(), provider={"kind": "chat", "name": "deterministic", "model": "structured_v1"})
        try:
            prefer_workbook = bool(re.search(r"\b(?:spreadsheet|sheet)\b", query, re.I) and not re.search(r"\bcsv\b", query, re.I))
            key, plan, effective_query, traces = structured.select_table(query, tables, prefer_workbook)
            units = tables[key]
            result = structured.execute(plan, units)
            fresh = [e for e in self.repository.all_evidence() if (e.document_id, e.page) == key]
            structured.verify_question_plan(effective_query, plan, result, fresh)
            structured.verify_execution(result, fresh)
            answer, citations = structured.answer_execution(query, result, units)
            selected_values = (" ".join(row.table_row.cells[i] for row in result.rows for i in plan.columns)
                               if plan.operation == "lookup" else structured.display_number(result.value))
            if _answer_type_missing(query, ["selected_values"], {"selected_values": selected_values}):
                raise structured.StructuredError("answer_type_missing", "The selected cells do not contain the requested number, amount or date.")
            return GroundedResponse(**response, outcome="grounded", answer=answer, grounded=True,
                citations=citations, retrieved_chunk_count=len(units),
                diagnostic={"structured_operation": plan.operation, "selected_rows": len(result.rows), "verified": True,
                            "plan_verified": True, "structured_plan": structured.plan_diagnostic(plan, units[0].table_row.headers),
                            "table_candidates": traces})
        except structured.StructuredError as exc:
            return GroundedResponse(**response, outcome="insufficient_evidence", answer=None, grounded=False,
                citations=[], retrieved_chunk_count=sum(len(t) for t in tables.values()),
                refusal_reason=exc.code, refusal_detail=str(exc), diagnostic=exc.diagnostic or None)

    def _ask_keys(self, query: str, scope: SearchScope | None) -> GroundedResponse | None:
        eligible, named = self._structured_candidates(query, scope)
        units = [e.model_copy(deep=True) for e in eligible if e.key_value]
        if not units:
            return None
        explicit = bool(re.search(r"\b(?:json|yaml|xml|config)\b", query, re.I) or named
                        or (scope and scope.type == "document"))
        response = dict(id=f"resp_{uuid4().hex[:12]}", kind="ask", query=query, created_at=utc_now(),
                        provider={"kind": "chat", "name": "deterministic", "model": "key_path_v1"})
        try:
            selected = structured.select_keys(query, units)
            values = " ".join(e.key_value.value for e in selected)
            if _answer_type_missing(query, ["selected_values"], {"selected_values": values}):
                raise structured.StructuredError("answer_type_missing", "The selected key values do not contain the requested number, amount or date.")
            fresh = {e.id: e for e in self.repository.all_evidence()}
            for old in selected:
                current = fresh.get(old.id)
                if current is None or current.key_value != old.key_value or current.snippet != old.key_value.quote():
                    raise structured.StructuredError("key_evidence_mismatch", "The selected path does not match stored evidence.")
                doc_units = [e for e in fresh.values() if e.document_id == old.document_id and e.key_value]
                if old.key_value.unit_count and len(doc_units) != old.key_value.unit_count:
                    raise structured.StructuredError("incomplete_keys", "The stored key paths are incomplete. Re-ingest the document.")
            citations = [Citation(id=f"cit_{uuid4().hex[:10]}", ordinal=i, evidence_unit_id=e.id,
                                  snippet=e.snippet, key_path=e.key_value.path) for i, e in enumerate(selected, 1)]
            return GroundedResponse(**response, outcome="grounded", answer="\n".join(e.snippet for e in selected),
                                    grounded=True, citations=citations, retrieved_chunk_count=len(units),
                                    diagnostic={"structured_operation": "key_lookup", "verified": True})
        except structured.StructuredError as exc:
            if not explicit and exc.code == "key_unmapped":
                return None
            return GroundedResponse(**response, outcome="insufficient_evidence", answer=None, grounded=False,
                                    citations=[], retrieved_chunk_count=len(units), refusal_reason=exc.code,
                                    refusal_detail=str(exc))

    def ask(self, query: str, scope: SearchScope | None = None) -> GroundedResponse:
        table_answer = self._ask_table(query, scope)
        if table_answer is not None:
            return table_answer
        key_answer = self._ask_keys(query, scope)
        if key_answer is not None:
            return key_answer
        total_started = perf_counter()
        stage_started = perf_counter()
        chunks = self.retrieve(query, scope)
        _log_stage("retrieval", stage_started, chunks=len(chunks))
        response_id = f"resp_{uuid4().hex[:12]}"
        now = utc_now()
        chat = self.registry.get_chat_provider()
        provider_meta = {
            "kind": "chat",
            "name": chat.ref["provider_type"],
            "model": chat.ref["model_name"],
        }
        if not chunks:
            _log_stage("total", total_started, outcome="insufficient_evidence", chunks=0)
            return GroundedResponse(
                id=response_id,
                kind="ask",
                query=query,
                outcome="insufficient_evidence",
                answer=None,
                grounded=False,
                citations=[],
                retrieved_chunk_count=0,
                provider=provider_meta,
                created_at=now,
                refusal_reason="insufficient_evidence",
                diagnostic={"top_score": 0.0, "threshold": self.settings.min_similarity},
            )
        term_document_frequency, document_count = self._idf_stats()
        if document_count >= 2 and chunks[0].lexical_coverage < self.settings.min_support:
            _log_stage("total", total_started, outcome="insufficient_evidence", reason="low_support")
            return GroundedResponse(
                id=response_id,
                kind="ask",
                query=query,
                outcome="insufficient_evidence",
                answer=None,
                grounded=False,
                citations=[],
                retrieved_chunk_count=len(chunks),
                provider=provider_meta,
                created_at=now,
                refusal_reason="low_support",
                diagnostic={
                    "top_score": chunks[0].score,
                    "threshold": self.settings.min_similarity,
                    "min_support": self.settings.min_support,
                    **self._retrieval_signals(chunks),
                    "top5": self._retrieval_top5(chunks),
                },
            )
        chunks = self._prioritize_hint_chunks(query, chunks)
        ask_chunks = chunks[: self.settings.ask_max_chunks]

        stage_started = perf_counter()
        prompt = build_ask_prompt(
            query,
            ask_chunks,
            max_chunks=self.settings.ask_max_chunks,
            max_chars=self.settings.ask_chunk_max_chars,
            context_window=self.settings.ask_num_ctx,
        )
        _log_stage("prompt_build", stage_started)
        try:
            stage_started = perf_counter()
            raw = _generate_chat(chat, prompt)
            _log_stage("model_call", stage_started, attempt=1, provider=chat.ref["provider_type"])
        except Exception:
            _log_stage("model_call", stage_started, attempt=1, provider=chat.ref["provider_type"], failed=True)
            logger.exception("Chat generation failed before grounding gate")
            # Missing model / Ollama failure: fall back to local extractive synthesis.
            from app.providers.extractive import ExtractiveChatAdapter

            chat = ExtractiveChatAdapter()
            provider_meta = {
                "kind": "chat",
                "name": chat.ref["provider_type"],
                "model": chat.ref["model_name"],
            }
            raw = chat.generate(prompt, stream=False)
        raw_text = raw if isinstance(raw, str) else "".join(raw)
        allowed = {str(index) for index, chunk in enumerate(ask_chunks, start=1)}
        evidence_by_id = {
            str(index): chunk.evidence.snippet[: self.settings.ask_chunk_max_chars]
            for index, chunk in enumerate(ask_chunks, start=1)
        }
        evidence_metadata = {
            str(index): chunk.evidence
            for index, chunk in enumerate(ask_chunks, start=1)
        }
        stage_started = perf_counter()
        gate = self.gate.validate(
            raw_text,
            allowed,
            task="ask",
            evidence_by_id=evidence_by_id,
            query=query,
            evidence_metadata=evidence_metadata,
            term_document_frequency=term_document_frequency,
            document_pages=self._document_pages(),
        )
        _log_stage("verification", stage_started, outcome=gate.outcome, reason=gate.reason or "none")
        model_rejected = (
            gate.reason
            if chat.ref["provider_type"] == "ollama" and gate.outcome != "grounded"
            else None
        )

        for retry in range(max(0, self.settings.ask_retries)) if chat.ref["provider_type"] == "ollama" else ():
            if gate.outcome == "grounded":
                break
            correction_prompt = (
                f"{prompt}\n\n"
                "Your previous response did not include a valid citation. Correct it now. "
                "Return exactly one concise sentence, and append [chunk:<id>] to every factual claim. "
                f"Valid chunk IDs are: {', '.join(sorted(allowed))}."
            )
            try:
                stage_started = perf_counter()
                corrected = _generate_chat(chat, correction_prompt)
                _log_stage("model_call", stage_started, attempt=retry + 2, provider=chat.ref["provider_type"])
                corrected_text = corrected if isinstance(corrected, str) else "".join(corrected)
                stage_started = perf_counter()
                gate = self.gate.validate(
                    corrected_text,
                    allowed,
                    task="ask",
                    evidence_by_id=evidence_by_id,
                    query=query,
                    evidence_metadata=evidence_metadata,
                    term_document_frequency=term_document_frequency,
                    document_pages=self._document_pages(),
                )
                _log_stage("verification", stage_started, attempt=retry + 2, outcome=gate.outcome, reason=gate.reason or "none")
                if gate.outcome == "grounded":
                    raw_text = corrected_text
                elif chat.ref["provider_type"] == "ollama":
                    model_rejected = gate.reason
            except Exception:
                _log_stage("model_call", stage_started, attempt=retry + 2, provider=chat.ref["provider_type"], failed=True)
                logger.exception("Corrective chat generation failed before grounding gate")

        # Small local models often answer without [chunk:id] markers. If we already
        # retrieved evidence, synthesize a grounded extractive answer instead of refusing.
        if (gate.outcome != "grounded" or gate.text is None) and chunks:
            from app.providers.extractive import ExtractiveChatAdapter

            term_documents: dict[str, set[str]] = {}
            for evidence in self.repository.evidence.values():
                terms = set(re.findall(r"[a-z0-9][a-z0-9_.-]*", evidence.snippet.lower()))
                for term in terms:
                    parts = re.findall(r"[a-z0-9]+", term)
                    for part in parts:
                        term_documents.setdefault(part, set()).add(evidence.document_id)
            term_document_frequency = {term: len(document_ids) for term, document_ids in term_documents.items()}
            document_count = len({evidence.document_id for evidence in self.repository.evidence.values()})
            extractive = ExtractiveChatAdapter(
                term_document_frequency=term_document_frequency,
                document_count=document_count,
            )
            provider_meta = {
                "kind": "chat",
                "name": extractive.ref["provider_type"],
                "model": extractive.ref["model_name"],
            }
            stage_started = perf_counter()
            raw = extractive.generate(prompt, stream=False)
            _log_stage("fallback", stage_started, provider=extractive.ref["provider_type"])
            raw_text = raw if isinstance(raw, str) else "".join(raw)
            stage_started = perf_counter()
            gate = self.gate.validate(
                raw_text,
                allowed,
                task="ask",
                evidence_by_id=evidence_by_id,
                query=query,
                evidence_metadata=evidence_metadata,
                term_document_frequency=term_document_frequency,
                document_pages=self._document_pages(),
            )
            _log_stage("verification", stage_started, attempt="fallback", outcome=gate.outcome, reason=gate.reason or "none")

        if gate.outcome != "grounded" or gate.text is None:
            _log_stage("total", total_started, outcome="insufficient_evidence", chunks=len(chunks))
            return GroundedResponse(
                id=response_id,
                kind="ask",
                query=query,
                outcome="insufficient_evidence",
                answer=None,
                grounded=False,
                citations=[],
                retrieved_chunk_count=len(chunks),
                provider=provider_meta,
                created_at=now,
                refusal_reason=gate.reason or "insufficient_evidence",
                diagnostic={
                    "top_score": max(chunk.score for chunk in chunks),
                    "threshold": self.settings.min_similarity,
                    **self._retrieval_signals(chunks),
                    "top5": self._retrieval_top5(chunks),
                    "model_rejected": model_rejected,
                },
            )

        stage_started = perf_counter()
        citation_ids = [
            ask_chunks[int(cited_id) - 1].evidence.id
            for cited_id in gate.cited_ids
            if cited_id.isdigit() and 0 < int(cited_id) <= len(ask_chunks)
        ]
        citations = self._bind_citations(citation_ids, chunks, query, gate.text or "")
        _log_stage("citation_binding", stage_started, citations=len(citations))
        quote_type_missing = _answer_type_missing(
            query,
            [citation.evidence_unit_id for citation in citations],
            {citation.evidence_unit_id: citation.snippet for citation in citations},
        )
        if not citations or quote_type_missing:
            _log_stage("total", total_started, outcome="insufficient_evidence", chunks=len(chunks))
            return GroundedResponse(
                id=response_id,
                kind="ask",
                query=query,
                outcome="insufficient_evidence",
                answer=None,
                grounded=False,
                citations=[],
                retrieved_chunk_count=len(chunks),
                provider=provider_meta,
                created_at=now,
                refusal_reason="answer_type_missing" if quote_type_missing else "citation_passage_missing",
                diagnostic={
                    "top_score": max(chunk.score for chunk in chunks),
                    "threshold": self.settings.min_similarity,
                    **self._retrieval_signals(chunks),
                    "top5": self._retrieval_top5(chunks),
                    "model_rejected": model_rejected,
                },
            )
        confidence = score_confidence(chunks, citation_ids)
        # Removing inline [chunk:id] markers leaves the whitespace that
        # preceded them, which otherwise shows up as "... 18 months ."
        cleaned = CITATION_RE.sub("", gate.text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned).strip()
        _log_stage("total", total_started, outcome="grounded", chunks=len(chunks))
        return GroundedResponse(
            id=response_id,
            kind="ask",
            query=query,
            outcome="grounded",
            answer=cleaned,
            grounded=True,
            citations=citations,
            retrieved_chunk_count=len(chunks),
            provider=provider_meta,
            created_at=now,
            diagnostic={
                "top_score": max(chunk.score for chunk in chunks),
                "threshold": self.settings.min_similarity,
                **self._retrieval_signals(chunks),
                "top5": self._retrieval_top5(chunks),
                "confidence": confidence.overall,
                "retrieval": confidence.retrieval,
                "coverage": confidence.coverage,
                "ocr": confidence.ocr,
                "model_rejected": model_rejected,
            },
        )

    def ask_stream_tokens(self, query: str, scope: SearchScope | None = None) -> tuple[GroundedResponse, Iterator[str]]:
        result = self.ask(query, scope)

        def tokens() -> Iterator[str]:
            if not result.answer:
                return
            parts = result.answer.split(" ")
            for index, token in enumerate(parts):
                suffix = " " if index < len(parts) - 1 else ""
                yield token + suffix

        return result, tokens()

    def _bind_citations(
        self, cited_ids: list[str], chunks: list[RetrievedChunk], query: str, answer: str
    ) -> list[Citation]:
        by_id = {chunk.evidence.id: chunk.evidence for chunk in chunks}
        citations: list[Citation] = []
        seen: set[str] = set()
        ordinal = 1
        answer_sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", answer) if part.strip()]
        for evidence_id in cited_ids:
            if evidence_id in seen:
                continue
            evidence = by_id.get(evidence_id)
            if evidence is None:
                continue
            seen.add(evidence_id)
            claim_parts: list[str] = []
            for index, part in enumerate(answer_sentences):
                if evidence_id in CITATION_RE.findall(part):
                    claim_parts.append(part)
                elif (
                    index > 0
                    and CITATION_RE.fullmatch(part.strip(" ."))
                    and evidence_id in CITATION_RE.findall(answer_sentences[index - 1])
                ):
                    claim_parts.append(answer_sentences[index - 1])
            snippet = select_evidence_passage(query, " ".join(claim_parts) or answer, evidence.snippet)
            if not snippet:
                # Derived answers may not repeat the source's literal values.
                # Use the query to select a source span, but never emit an
                # unverified empty citation.
                snippet = select_evidence_passage(query, query, evidence.snippet)
            if snippet and not _answer_value_is_cited(answer, snippet):
                snippet = _select_answer_value_passage(answer, evidence.snippet)
            if snippet and not _answer_value_is_cited(answer, snippet):
                logger.warning("Citation %s does not contain a specific answer value; dropping citation", evidence.id)
                snippet = ""
            if not snippet:
                logger.warning("No precise source passage matched citation %s; dropping citation", evidence.id)
                continue
            citations.append(
                Citation(
                    id=f"cit_{uuid4().hex[:10]}",
                    ordinal=ordinal,
                    evidence_unit_id=evidence.id,
                    snippet=snippet,
                )
            )
            ordinal += 1
        return citations


def _answer_value_is_cited(answer: str, snippet: str) -> bool:
    """Require distinctive answer values, such as markers, in displayed evidence."""
    answer_terms = {
        term.lower().rstrip(".,;:!?")
        for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", CITATION_RE.sub("", answer))
        if len(term) >= 6 and any(char.isdigit() for char in term)
    }
    if not answer_terms:
        return True
    if re.search(r"\b(?:total|sum|average|mean|count)\b", answer, re.I) and all(
        term.isdigit() for term in answer_terms
    ):
        return True
    snippet_terms = {
        term.lower()
        for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", snippet)
    }
    return answer_terms <= snippet_terms


def _select_answer_value_passage(answer: str, source: str) -> str:
    value_terms = {
        term.lower().rstrip(".,;:!?")
        for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", CITATION_RE.sub("", answer))
        if len(term) >= 6 and any(char.isdigit() for char in term)
    }
    if not value_terms:
        return ""
    for passage in re.split(r"(?<=[.!?])\s+|\n+", source):
        passage_terms = {
            term.lower().rstrip(".,;:!?")
            for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", passage)
        }
        if value_terms <= passage_terms:
            return passage.strip()
    return ""
