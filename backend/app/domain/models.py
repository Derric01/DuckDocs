"""Typed API/domain models.

Implements the stable resource shapes in docs/15_API_SPECIFICATION.md §8 and
the evidence invariants in docs/03_FUNCTIONAL_REQUIREMENTS.md §7.2.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


DocumentState = Literal["ready", "processing", "review", "failed"]
JobState = Literal["queued", "processing", "ready", "failed", "cancelled"]
FidelityTier = Literal["full_layout", "structural", "ocr_dependent", "best_effort"]
Relevance = Literal["High", "Medium", "Low"]


class TableRow(BaseModel):
    """Ordered cells retain blank/duplicate headers and physical row coordinates."""
    model_config = ConfigDict(extra="forbid")
    headers: list[str]
    cells: list[str]
    sheet_name: str | None = None
    row_number: int = Field(ge=1)
    data_row_count: int = Field(ge=0)
    is_header: bool = False

    def quote(self) -> str:
        prefix = f"Sheet: {self.sheet_name}\n" if self.sheet_name else ""
        values = " | ".join(f"{header}: {cell}" for header, cell in zip(self.headers, self.cells))
        return f"{prefix}Row {self.row_number}: {values}"


class KeyValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    keys: list[str]
    value: str
    value_type: str
    unit_count: int = Field(default=0, ge=0)

    def quote(self) -> str:
        return f"{self.path}: {self.value}"


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
    file_type: str | None = None
    table_row: TableRow | None = None
    key_value: KeyValue | None = None
    paragraph_number: int | None = Field(default=None, ge=1)


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
    # Generated at ingest. `summary_method` records how it was produced so the
    # UI can distinguish verbatim sentences from model-written prose.
    summary: str | None = None
    summary_method: Literal["extractive", "abstractive"] | None = None
    summary_provider: str | None = None


class IngestJob(BaseModel):
    id: str
    document_id: str
    status: JobState
    stage: Literal[
        "queued", "parsing", "ocr", "chunking", "summarizing", "embedding", "indexing", "ready", "failed"
    ]
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
    sheet_name: str | None = None
    row_number: int | None = None
    column: str | None = None
    key_path: str | None = None


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
    refusal_detail: str | None = None
    diagnostic: dict[str, Any] | None = None


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
