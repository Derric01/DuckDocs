"""Chroma-backed vector store with graceful offline fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.core.config import Settings
from app.domain.models import Evidence
from app.providers.base import EmbeddingProviderAdapter


@dataclass(slots=True)
class RetrievedChunk:
    evidence: Evidence
    score: float


class VectorStore:
    """Indexes and retrieves evidence embeddings.

    When Chroma is unavailable or the embedding provider is the keyword stub,
    callers should fall back to DocumentRepository.search_evidence.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any | None = None
        self._collection: Any | None = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        try:
            import chromadb
        except ImportError:
            self._available = False
            return
        try:
            if self.settings.chroma_url:
                parsed = urlparse(self.settings.chroma_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 8000
                self._client = chromadb.HttpClient(host=host, port=port)
            else:
                persist_path = str(self.settings.data_root / "vectors")
                self._client = chromadb.PersistentClient(path=persist_path)
            self._collection = self._client.get_or_create_collection(
                name="duckdocs_evidence",
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
        except Exception:
            self._client = None
            self._collection = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._collection is not None

    def health(self) -> str:
        return "ok" if self.available else "unavailable"

    def upsert_evidence(self, evidence_units: list[Evidence], embedder: EmbeddingProviderAdapter) -> int:
        if not self.available or not evidence_units:
            return 0
        if embedder.ref["provider_type"] == "keyword":
            return 0
        try:
            texts = [unit.snippet for unit in evidence_units]
            embeddings = embedder.embed(texts)
            if not embeddings or not embeddings[0]:
                return 0
            assert self._collection is not None
            self._collection.upsert(
                ids=[unit.id for unit in evidence_units],
                embeddings=embeddings,
                documents=texts,
                metadatas=[
                    {
                        "document_id": unit.document_id,
                        "document_name": unit.document_name,
                        "section": unit.section,
                        "page": unit.page,
                        "line_start": unit.line_start,
                        "line_end": unit.line_end,
                    }
                    for unit in evidence_units
                ],
            )
            return len(evidence_units)
        except Exception:
            return 0

    def delete_document(self, document_id: str) -> None:
        if not self.available:
            return
        try:
            assert self._collection is not None
            existing = self._collection.get(where={"document_id": document_id})
            ids = existing.get("ids") or []
            if ids:
                self._collection.delete(ids=ids)
        except Exception:
            return

    def query(
        self,
        query: str,
        embedder: EmbeddingProviderAdapter,
        evidence_lookup: dict[str, Evidence],
        *,
        top_k: int,
        min_similarity: float,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not self.available or embedder.ref["provider_type"] == "keyword":
            return []
        try:
            vectors = embedder.embed([query])
            if not vectors or not vectors[0]:
                return []
            where = {"document_id": {"$in": document_ids}} if document_ids else None
            assert self._collection is not None
            result = self._collection.query(
                query_embeddings=vectors,
                n_results=top_k,
                where=where,
                include=["distances", "metadatas", "documents"],
            )
            ids = (result.get("ids") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            chunks: list[RetrievedChunk] = []
            for evidence_id, distance in zip(ids, distances, strict=False):
                score = max(0.0, min(1.0, 1.0 - float(distance)))
                if score < min_similarity:
                    continue
                evidence = evidence_lookup.get(evidence_id)
                if evidence is None:
                    continue
                chunks.append(
                    RetrievedChunk(
                        evidence=evidence.model_copy(update={"retrieval_score": score}),
                        score=score,
                    )
                )
            return chunks
        except Exception:
            return []
