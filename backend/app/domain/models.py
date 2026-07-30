"""Typed API/domain models.

Implements the stable resource shapes in docs/15_API_SPECIFICATION.md §8 and
the evidence invariants in docs/03_FUNCTIONAL_REQUIREMENTS.md §7.2.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


DocumentState = Literal["ready", "processing", "review", "failed"]
JobState = Literal["queued", "processing", "ready", "failed", "cancelled"]
FidelityTier = Literal["full_layout", "structural", "ocr_dependent", "best_effort"]
Relevance = Literal["High", "Medium", "Low"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    document_name: str
    section: str
    page: int
    line_start: int
    line_end: int
    snippet: str
    retrieval_score: float = Field(ge=0, le=1)
    relevance: Relevance
    anchor_quality: Literal["line", "paragraph", "bbox", "cell"] = "line"
    fidelity_tier: FidelityTier = "full_layout"
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_engine: str | None = None
    # Normalized page-relative box (x, y, width, height), top-left origin.
    bbox: tuple[float, float, float, float] | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    file_type: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    status: DocumentState
    fidelity_tier: FidelityTier
    pages: int = Field(ge=1)
    category: str
    current_version_id: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)


class IngestJob(BaseModel):
    id: str
    document_id: str
    status: JobState
    stage: Literal["queued", "parsing", "ocr", "chunking", "embedding", "indexing", "ready", "failed"]
    progress_pct: int = Field(ge=0, le=100)
    error: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedDocuments(BaseModel):
    items: list[Document]
    next_cursor: str | None = None
    has_more: bool = False


class UploadItem(BaseModel):
    document: Document
    ingest_job_id: str


class UploadResponse(BaseModel):
    items: list[UploadItem]


class SearchScope(BaseModel):
    type: Literal["library", "document", "selection"] = "library"
    document_id: str | None = None
    document_ids: list[str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    scope: SearchScope = Field(default_factory=SearchScope)
    top_k: int = Field(default=20, ge=1, le=100)
    filters: dict[str, list[str]] = Field(default_factory=dict)


class SearchResult(BaseModel):
    evidence: Evidence
    snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    embedding_provider: dict[str, str]


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    scope: SearchScope = Field(default_factory=SearchScope)
    stream: bool = False


class Citation(BaseModel):
    id: str
    ordinal: int
    evidence_unit_id: str
    snippet: str


class GroundedResponse(BaseModel):
    id: str
    kind: Literal["ask", "summarize", "extract"]
    query: str
    outcome: Literal["grounded", "insufficient_evidence"]
    answer: str | None
    grounded: bool
    citations: list[Citation]
    retrieved_chunk_count: int
    provider: dict[str, str]
    created_at: datetime
    refusal_reason: str | None = None
    diagnostic: dict[str, float] | None = None


class Provider(BaseModel):
    id: str
    kind: Literal["chat", "embedding"]
    name: str
    model: str
    configured: bool
    connected: bool
    local: bool


class ProviderConfigRequest(BaseModel):
    role: Literal["chat", "embedding"]
    provider_type: Literal["ollama", "openai", "anthropic", "gemini", "openai_compatible", "extractive", "keyword"]
    model_name: str = ""
    base_url: str | None = None
    api_key: str | None = None
    is_default: bool = False


class ProviderConfigResponse(BaseModel):
    id: str
    role: Literal["chat", "embedding"]
    provider_type: str
    model_name: str
    base_url: str | None = None
    api_key_ref: str | None = None
    is_default: bool = False
    connected: bool = False
    local: bool = True


class ProviderTestResponse(BaseModel):
    reachable: bool
    latency_ms: float | None = None
    error: str | None = None


class SettingsResponse(BaseModel):
    theme: Literal["dark", "light"] = "dark"
    density: Literal["dense", "comfortable"] = "dense"
    local_only: bool = True
    providers: list[Provider]

