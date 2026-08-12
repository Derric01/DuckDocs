"""RAG grounding pipeline (docs/11_RAG_ARCHITECTURE.md)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from app.core.config import Settings
from app.domain.models import Citation, GroundedResponse, SearchScope, utc_now
from app.providers.registry import ProviderRegistry
from app.repositories import AnyRepository
from app.services.vector_store import RetrievedChunk, VectorStore

CITATION_RE = re.compile(r"\[chunk:([^\]]+)\]")


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
    def validate(self, raw_output: str, allowed_chunk_ids: set[str], task: str = "ask") -> GateResult:
        stripped = raw_output.strip()
        if stripped == "INSUFFICIENT_EVIDENCE" or stripped.startswith("INSUFFICIENT_EVIDENCE"):
            return GateResult(outcome="insufficient_evidence", text=None, cited_ids=[], reason="model_declined")

        cited_ids = CITATION_RE.findall(raw_output)
        unknown = set(cited_ids) - allowed_chunk_ids
        if unknown:
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="gate_rejected_output",
            )

        if task == "ask" and cited_ids:
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
            factual = [sentence for sentence in sentences if _looks_factual(sentence)]
            uncited = [sentence for sentence in factual if not CITATION_RE.search(sentence)]
            if factual and len(uncited) / max(1, len(factual)) > 0.6:
                return GateResult(
                    outcome="insufficient_evidence",
                    text=None,
                    cited_ids=cited_ids,
                    reason="citation_density_low",
                )

        if not cited_ids and task == "ask":
            return GateResult(
                outcome="insufficient_evidence",
                text=None,
                cited_ids=[],
                reason="citation_density_low",
            )

        return GateResult(outcome="grounded", text=raw_output, cited_ids=list(dict.fromkeys(cited_ids)))


def _looks_factual(sentence: str) -> bool:
    lowered = sentence.lower().strip()
    if lowered.startswith(
        ("in summary", "overall", "therefore", "thus", "based on the retrieved", "i found the strongest")
    ):
        return False
    if CITATION_RE.fullmatch(lowered.strip(" .")):
        return False
    return any(char.isdigit() for char in sentence) or len(sentence.split()) > 6


def build_ask_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for chunk in chunks:
        blocks.append(
            f"[[chunk:{chunk.evidence.id}]]\n{chunk.evidence.snippet}\n[[/chunk]]"
        )
    context = "\n\n".join(blocks)
    return (
        "You are DuckDocs Waymark. Answer ONLY from the provided context.\n"
        "Cite every factual claim with [chunk:<id>] using only IDs present in the context.\n"
        "If the context is insufficient, reply with exactly INSUFFICIENT_EVIDENCE.\n\n"
        f"Question: {query}\n\nContext:\n{context}\n\nAnswer:"
    )


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
        if vector_hits:
            return self._dedupe_chunks(vector_hits)

        # Keyword fallback (always available offline).
        keyword_hits = self.repository.search_evidence(query, self.settings.top_k)
        if document_ids:
            keyword_hits = [item for item in keyword_hits if item.document_id in document_ids]
        return self._dedupe_chunks(
            [
                RetrievedChunk(evidence=item, score=max(item.retrieval_score, 0.4))
                for item in keyword_hits
            ]
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
        self.vector_store.delete_document(document_id)
        embedder = self.registry.get_embedding_provider()
        return self.vector_store.upsert_evidence(units, embedder)

    def ask(self, query: str, scope: SearchScope | None = None) -> GroundedResponse:
        chunks = self.retrieve(query, scope)
        response_id = f"resp_{uuid4().hex[:12]}"
        now = utc_now()
        chat = self.registry.get_chat_provider()
        provider_meta = {
            "kind": "chat",
            "name": chat.ref["provider_type"],
            "model": chat.ref["model_name"],
        }
        if not chunks:
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

        prompt = build_ask_prompt(query, chunks)
        try:
            raw = chat.generate(prompt, stream=False)
        except Exception:
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
        allowed = {chunk.evidence.id for chunk in chunks}
        gate = self.gate.validate(raw_text, allowed, task="ask")

        # Small local models often answer without [chunk:id] markers. If we already
        # retrieved evidence, synthesize a grounded extractive answer instead of refusing.
        if (gate.outcome != "grounded" or gate.text is None) and chunks:
            from app.providers.extractive import ExtractiveChatAdapter

            extractive = ExtractiveChatAdapter()
            provider_meta = {
                "kind": "chat",
                "name": extractive.ref["provider_type"],
                "model": extractive.ref["model_name"],
            }
            raw = extractive.generate(prompt, stream=False)
            raw_text = raw if isinstance(raw, str) else "".join(raw)
            gate = self.gate.validate(raw_text, allowed, task="ask")

        if gate.outcome != "grounded" or gate.text is None:
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

        citations = self._bind_citations(gate.cited_ids, chunks)
        confidence = score_confidence(chunks, gate.cited_ids)
        # Removing inline [chunk:id] markers leaves the whitespace that
        # preceded them, which otherwise shows up as "... 18 months ."
        cleaned = CITATION_RE.sub("", gate.text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned).strip()
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

    def _bind_citations(self, cited_ids: list[str], chunks: list[RetrievedChunk]) -> list[Citation]:
        by_id = {chunk.evidence.id: chunk.evidence for chunk in chunks}
        citations: list[Citation] = []
        seen: set[str] = set()
        ordinal = 1
        for evidence_id in cited_ids:
            if evidence_id in seen:
                continue
            evidence = by_id.get(evidence_id)
            if evidence is None:
                continue
            seen.add(evidence_id)
            citations.append(
                Citation(
                    id=f"cit_{uuid4().hex[:10]}",
                    ordinal=ordinal,
                    evidence_unit_id=evidence.id,
                    snippet=evidence.snippet,
                )
            )
            ordinal += 1
        return citations
