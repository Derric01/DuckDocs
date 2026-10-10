"""RAG grounding pipeline (docs/11_RAG_ARCHITECTURE.md)."""

from __future__ import annotations

import logging
import json
import os
import re
from time import perf_counter
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations
from difflib import SequenceMatcher
from typing import Literal
from uuid import uuid4

from app.core.config import Settings
from app.domain.models import Citation, Evidence, GroundedResponse, SearchScope, utc_now
from app.providers.registry import ProviderRegistry
from app.repositories import AnyRepository
from app.services.vector_store import RetrievedChunk, VectorStore, relevance_bucket

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
        return generate(prompt, stream=False, structured_output=True)
    return generate(prompt, stream=False)


def _log_stage(stage: str, started: float, **fields: object) -> None:
    logger.debug("ask_stage=%s duration_ms=%.1f %s", stage, (perf_counter() - started) * 1000, " ".join(
        f"{key}={value}" for key, value in fields.items()
    ))


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
    ) -> GateResult:
        stripped = raw_output.strip()
        if stripped == "INSUFFICIENT_EVIDENCE" or stripped.startswith("INSUFFICIENT_EVIDENCE"):
            return GateResult(outcome="insufficient_evidence", text=None, cited_ids=[], reason="model_declined")

        structured = _parse_structured_claims(stripped)
        if structured is not None:
            verified: list[tuple[str, str]] = []
            for claim, evidence_id, quote in structured:
                if evidence_id not in allowed_chunk_ids or not evidence_by_id:
                    continue
                source = evidence_by_id.get(evidence_id, "")
                if _evidence_matches_query_hints(query, evidence_metadata, evidence_id) and _quote_matches(quote, source):
                    verified.append((claim, evidence_id))
            if not verified:
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="no_verified_claims",
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
            cited_ids = [
                evidence_id
                for evidence_id in cited_ids
                if _evidence_matches_query_hints(query, evidence_metadata, evidence_id)
            ]
            if (
                not answer
                or not cited_ids
                or any(cited_id not in allowed_chunk_ids for cited_id in cited_ids)
                or not evidence_by_id
                or any(not evidence_by_id.get(cited_id, "").strip() for cited_id in cited_ids)
                or _looks_like_junk_output(answer, query)
                or not _claims_match_evidence([answer], cited_ids, evidence_by_id)
            ):
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=[],
                    reason="no_verified_claims",
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
            if _evidence_matches_query_hints(query, evidence_metadata, evidence_id)
        ]

        if task == "ask" and cited_ids:
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
            if factual and len(uncited) / max(1, len(factual)) > 0.6:
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
                reason="no_verified_claims",
            )
        return GateResult(outcome="grounded", text=raw_output, cited_ids=list(dict.fromkeys(cited_ids)))


def _parse_structured_claims(raw_output: str) -> list[tuple[str, str, str]] | None:
    if not raw_output.startswith("{"):
        return None
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return []
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
) -> bool:
    if not query or not evidence_metadata:
        return True
    evidence = evidence_metadata.get(evidence_id)
    if evidence is None:
        return True
    lowered = query.lower()
    name = evidence.document_name.lower()
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    if "yaml" in lowered and extension not in {"yaml", "yml"}:
        return False
    if "xml" in lowered and extension != "xml":
        return False
    if "spreadsheet" in lowered and extension not in {"xlsx", "xls", "csv"}:
        return False
    if "presentation" in lowered and extension not in {"pptx", "ppt"}:
        return False
    if "word document" in lowered and extension not in {"docx", "doc"}:
        return False
    if "native text pdf" in lowered and (extension != "pdf" or evidence.fidelity_tier == "ocr_dependent"):
        return False
    if "scanned" in lowered and evidence.ocr_confidence is None:
        return False
    page_match = re.search(r"\bpage\s+(\d+)\b", lowered)
    if page_match and evidence.page != int(page_match.group(1)):
        return False
    slide_match = re.search(r"\bslide\s+(\d+)\b", lowered)
    if slide_match and (extension not in {"pptx", "ppt"} or evidence.page != int(slide_match.group(1))):
        return False
    return True


def _quote_matches(quote: str, source: str) -> bool:
    normalized_quote = " ".join(quote.lower().split())
    normalized_source = " ".join(source.lower().split())
    if not normalized_quote or not normalized_source:
        return False
    if normalized_quote in normalized_source:
        return True
    return SequenceMatcher(None, normalized_quote, normalized_source).ratio() >= 0.9


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
        return set(re.findall(r"[a-z0-9]+(?:[_.-][a-z0-9]+)*", value.lower()))

    answer_terms = {
        term for term in tokenize(clean_answer) if term not in _EVIDENCE_STOP_WORDS and len(term) > 2
    }
    query_terms = {
        term for term in tokenize(query) if term not in _EVIDENCE_STOP_WORDS and len(term) > 2
    }
    if not answer_terms:
        return ""

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
    query_terms &= source_terms
    # Keep the citation tied to the subject asked about. If the retrieved
    # chunk does not contain any non-generic query term, it cannot support a
    # passage for this answer even if unrelated answer words happen to match.
    if not query_terms or not (query_terms & answer_terms):
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
        return " ".join(dict.fromkeys(selected))
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

        embedder = self.registry.get_embedding_provider()
        vector_hits = self.vector_store.query(
            query,
            embedder,
            self.repository.evidence,
            top_k=self.settings.top_k,
            min_similarity=self.settings.min_similarity,
            document_ids=document_ids,
        )
        keyword_hits = self.repository.search_evidence(query, self.settings.top_k)
        if document_ids:
            keyword_hits = [item for item in keyword_hits if item.document_id in document_ids]
        keyword_chunks = [
            self._keyword_chunk(query, item)
            for item in keyword_hits
            if self._has_lexical_support(query, item.snippet, item.document_name)
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
                )
            )
        result = self._dedupe_chunks(sorted(ranked, key=lambda item: item.score, reverse=True)[: self.settings.top_k])
        if self.settings.reranker == "lexical":
            result.sort(key=lambda item: (self._keyword_chunk(query, item.evidence).score, item.score), reverse=True)
        logger.debug(
            "retrieval_top5=%s",
            [(chunk.evidence.document_name, round(chunk.score, 4)) for chunk in result[:5]],
        )
        return result

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
        page_match = re.search(r"\bpage\s+(\d+)\b", lowered)
        if page_match and evidence.page == int(page_match.group(1)):
            boost += 0.25
        slide_match = re.search(r"\bslide\s+(\d+)\b", lowered)
        if slide_match and evidence.page == int(slide_match.group(1)) and name.rsplit(".", 1)[-1] in {"pptx", "ppt"}:
            boost += 0.25
        return boost

    @classmethod
    def _prioritize_hint_chunks(cls, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        hinted = [chunk for chunk in chunks if _evidence_matches_query_hints(query, {chunk.evidence.id: chunk.evidence}, chunk.evidence.id)]
        if not hinted or len(hinted) == len(chunks):
            return chunks
        hinted_ids = {chunk.evidence.id for chunk in hinted}
        return hinted + [chunk for chunk in chunks if chunk.evidence.id not in hinted_ids]

    @staticmethod
    def _has_lexical_support(query: str, snippet: str, document_name: str = "") -> bool:
        query_terms = {
            term
            for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", query.lower())
            if term not in _RETRIEVAL_SUPPORT_STOP_WORDS
        }
        if not query_terms:
            return False
        snippet_terms = set(re.findall(r"[a-z0-9][a-z0-9_.-]*", f"{document_name} {snippet}".lower()))
        matches = sum(term in snippet_terms for term in query_terms)
        if document_name and any(term == document_name.lower() for term in query_terms):
            return True
        return matches >= (1 if len(query_terms) == 1 else 2)

    def _keyword_chunk(self, query: str, evidence: Evidence) -> RetrievedChunk:
        terms = {term for term in re.findall(r"[a-z0-9][a-z0-9_.-]*", query.lower()) if len(term) > 2}
        haystack = f"{evidence.document_name} {evidence.section} {evidence.snippet}".lower()
        matched = sum(term in haystack for term in terms)
        score = matched / max(1, len(terms))
        return RetrievedChunk(
            evidence=evidence.model_copy(
                update={
                    "retrieval_score": score,
                    "relevance": relevance_bucket(score, self.settings),
                }
            ),
            score=score,
        )

    @staticmethod
    def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for chunk in chunks:
            key = " ".join(chunk.evidence.snippet.lower().split())[:240]
            if not key or key in seen:
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

    def ask(self, query: str, scope: SearchScope | None = None) -> GroundedResponse:
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
        chunks = self._prioritize_hint_chunks(query, chunks)

        stage_started = perf_counter()
        prompt = build_ask_prompt(
            query,
            chunks,
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
        allowed = {str(index) for index, chunk in enumerate(chunks[: self.settings.ask_max_chunks], start=1)}
        evidence_by_id = {
            str(index): chunk.evidence.snippet
            for index, chunk in enumerate(chunks[: self.settings.ask_max_chunks], start=1)
        }
        evidence_metadata = {
            str(index): chunk.evidence
            for index, chunk in enumerate(chunks[: self.settings.ask_max_chunks], start=1)
        }
        stage_started = perf_counter()
        gate = self.gate.validate(
            raw_text,
            allowed,
            task="ask",
            evidence_by_id=evidence_by_id,
            query=query,
            evidence_metadata=evidence_metadata,
        )
        _log_stage("verification", stage_started, outcome=gate.outcome, reason=gate.reason or "none")

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
                )
                _log_stage("verification", stage_started, attempt=retry + 2, outcome=gate.outcome, reason=gate.reason or "none")
                if gate.outcome == "grounded":
                    raw_text = corrected_text
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
                },
            )

        stage_started = perf_counter()
        citation_ids = [
            chunks[int(cited_id) - 1].evidence.id
            for cited_id in gate.cited_ids
            if cited_id.isdigit() and 0 < int(cited_id) <= min(len(chunks), self.settings.ask_max_chunks)
        ]
        citations = self._bind_citations(citation_ids, chunks, query, gate.text or "")
        _log_stage("citation_binding", stage_started, citations=len(citations))
        if not citations:
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
                refusal_reason="no_verified_claims",
                diagnostic={
                    "top_score": max(chunk.score for chunk in chunks),
                    "threshold": self.settings.min_similarity,
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
                "confidence": confidence.overall,
                "retrieval": confidence.retrieval,
                "coverage": confidence.coverage,
                "ocr": confidence.ocr,
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
