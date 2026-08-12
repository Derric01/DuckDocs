"""Optional PostgreSQL repository selected via DUCKDOCS_DB_URL."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.models import Document, Evidence, IngestJob, utc_now
from app.repositories.memory import DocumentRepository
from app.services.chunking import ChunkCandidate

try:
    from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, select
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _SQLALCHEMY_AVAILABLE = False


if _SQLALCHEMY_AVAILABLE:

    class Base(DeclarativeBase):
        pass

    class DocumentRow(Base):
        __tablename__ = "documents"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        name: Mapped[str] = mapped_column(String(512))
        file_type: Mapped[str] = mapped_column(String(32))
        mime_type: Mapped[str] = mapped_column(String(128))
        size_bytes: Mapped[int] = mapped_column(Integer)
        status: Mapped[str] = mapped_column(String(32))
        fidelity_tier: Mapped[str] = mapped_column(String(32))
        pages: Mapped[int] = mapped_column(Integer)
        category: Mapped[str] = mapped_column(String(128))
        current_version_id: Mapped[str] = mapped_column(String(64))
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
        tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
        summary: Mapped[str | None] = mapped_column(Text, nullable=True)
        summary_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
        summary_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)

    class JobRow(Base):
        __tablename__ = "ingest_jobs"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        document_id: Mapped[str] = mapped_column(String(64), index=True)
        status: Mapped[str] = mapped_column(String(32))
        stage: Mapped[str] = mapped_column(String(32))
        progress_pct: Mapped[int] = mapped_column(Integer)
        error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    class EvidenceRow(Base):
        __tablename__ = "evidence"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        document_id: Mapped[str] = mapped_column(String(64), index=True)
        document_name: Mapped[str] = mapped_column(String(512))
        section: Mapped[str] = mapped_column(String(256))
        page: Mapped[int] = mapped_column(Integer)
        line_start: Mapped[int] = mapped_column(Integer)
        line_end: Mapped[int] = mapped_column(Integer)
        snippet: Mapped[str] = mapped_column(Text)
        retrieval_score: Mapped[float] = mapped_column(Float)
        relevance: Mapped[str] = mapped_column(String(16))
        anchor_quality: Mapped[str] = mapped_column(String(32), default="line")
        fidelity_tier: Mapped[str] = mapped_column(String(32), default="full_layout")
        ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
        ocr_engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
        bbox: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    class ProviderConfigRow(Base):
        __tablename__ = "provider_configs"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        role: Mapped[str] = mapped_column(String(16))
        provider_type: Mapped[str] = mapped_column(String(32))
        model_name: Mapped[str] = mapped_column(String(128))
        base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
        api_key_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
        is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class SqlDocumentRepository:
    """SQLAlchemy-backed repository with the same surface as DocumentRepository."""

    def __init__(self, db_url: str) -> None:
        if not _SQLALCHEMY_AVAILABLE:
            raise RuntimeError("sqlalchemy is not installed; install backend extras to enable DUCKDOCS_DB_URL")
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(self.engine)
        self.documents: dict[str, Document] = {}
        self.jobs: dict[str, IngestJob] = {}
        self.evidence: dict[str, Evidence] = {}
        self._hydrate()

    def _hydrate(self) -> None:
        with self.SessionLocal() as session:
            self.documents = {row.id: self._to_document(row) for row in session.scalars(select(DocumentRow))}
            self.jobs = {row.id: self._to_job(row) for row in session.scalars(select(JobRow))}
            self.evidence = {row.id: self._to_evidence(row) for row in session.scalars(select(EvidenceRow))}

    def list_documents(self) -> list[Document]:
        self._hydrate()
        return list(self.documents.values())

    def get_document(self, document_id: str) -> Document | None:
        self._hydrate()
        return self.documents.get(document_id)

    def add_document(self, document: Document, job: IngestJob) -> None:
        with self.SessionLocal() as session:
            session.merge(self._from_document(document))
            session.merge(self._from_job(job))
            session.commit()
        self.documents[document.id] = document
        self.jobs[job.id] = job

    def index_document_chunks(
        self, document_id: str, chunks: list[ChunkCandidate], ocr_engine: str | None = None
    ) -> int:
        document = self.get_document(document_id)
        if document is None:
            return 0
        with self.SessionLocal() as session:
            existing = session.scalars(select(EvidenceRow).where(EvidenceRow.document_id == document_id)).all()
            for row in existing:
                session.delete(row)
            new_ids: set[str] = set()
            for index, chunk in enumerate(chunks, start=1):
                evidence_id = f"ev_{document_id.removeprefix('doc_')}_{index:04d}"
                new_ids.add(evidence_id)
                evidence = Evidence(
                    id=evidence_id,
                    document_id=document_id,
                    document_name=document.name,
                    section="Imported content",
                    page=chunk.page,
                    line_start=chunk.line_start,
                    line_end=chunk.line_end,
                    snippet=chunk.text[:4000],
                    retrieval_score=0.74,
                    relevance="Medium",
                    anchor_quality=chunk.anchor_quality,
                    fidelity_tier=chunk.fidelity_tier,
                    ocr_confidence=chunk.ocr_confidence,
                    ocr_engine=ocr_engine if chunk.ocr_confidence is not None else None,
                    bbox=chunk.bbox,
                )
                session.merge(self._from_evidence(evidence))
                self.evidence[evidence_id] = evidence
            session.commit()
        for evidence_id in [
            evidence_id
            for evidence_id, evidence in self.evidence.items()
            if evidence.document_id == document_id and evidence_id not in new_ids
        ]:
            del self.evidence[evidence_id]
        return len(chunks)

    def get_job(self, job_id: str) -> IngestJob | None:
        self._hydrate()
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, **changes: object) -> IngestJob | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={**changes, "updated_at": utc_now()})
        with self.SessionLocal() as session:
            session.merge(self._from_job(updated))
            session.commit()
        self.jobs[job_id] = updated
        return updated

    def update_document(self, document_id: str, **changes: object) -> Document | None:
        document = self.get_document(document_id)
        if document is None:
            return None
        updated = document.model_copy(update={**changes, "updated_at": utc_now()})
        with self.SessionLocal() as session:
            session.merge(self._from_document(updated))
            session.commit()
        self.documents[document_id] = updated
        return updated

    def search_evidence(self, query: str, limit: int) -> list[Evidence]:
        self._hydrate()
        terms = {term for term in query.lower().split() if len(term) > 2}
        if not terms:
            return []
        ranked = sorted(self.evidence.values(), key=lambda item: self._score(item, terms), reverse=True)
        return [
            item
            for item in ranked
            if any(
                term in item.snippet.lower() or term in item.section.lower() or term in item.document_name.lower()
                for term in terms
            )
        ][:limit]

    def all_evidence(self) -> Iterable[Evidence]:
        self._hydrate()
        return self.evidence.values()

    @staticmethod
    def _score(evidence: Evidence, terms: set[str]) -> int:
        haystack = f"{evidence.document_name} {evidence.section} {evidence.snippet}".lower()
        return sum(2 if term in evidence.snippet.lower() else int(term in haystack) for term in terms)

    @staticmethod
    def _to_document(row: DocumentRow) -> Document:
        return Document.model_validate(
            {
                "id": row.id,
                "name": row.name,
                "file_type": row.file_type,
                "mime_type": row.mime_type,
                "size_bytes": row.size_bytes,
                "status": row.status,
                "fidelity_tier": row.fidelity_tier,
                "pages": row.pages,
                "category": row.category,
                "current_version_id": row.current_version_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "tags": row.tags or [],
                "summary": row.summary,
                "summary_method": row.summary_method,
                "summary_provider": row.summary_provider,
            }
        )

    @staticmethod
    def _from_document(document: Document) -> DocumentRow:
        return DocumentRow(**document.model_dump())

    @staticmethod
    def _to_job(row: JobRow) -> IngestJob:
        return IngestJob.model_validate(
            {
                "id": row.id,
                "document_id": row.document_id,
                "status": row.status,
                "stage": row.stage,
                "progress_pct": row.progress_pct,
                "error": row.error,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    @staticmethod
    def _from_job(job: IngestJob) -> JobRow:
        return JobRow(**job.model_dump())

    @staticmethod
    def _to_evidence(row: EvidenceRow) -> Evidence:
        return Evidence.model_validate(
            {
                "id": row.id,
                "document_id": row.document_id,
                "document_name": row.document_name,
                "section": row.section,
                "page": row.page,
                "line_start": row.line_start,
                "line_end": row.line_end,
                "snippet": row.snippet,
                "retrieval_score": row.retrieval_score,
                "relevance": row.relevance,
                "anchor_quality": row.anchor_quality,
                "fidelity_tier": row.fidelity_tier,
                "ocr_confidence": row.ocr_confidence,
                "ocr_engine": row.ocr_engine,
                "bbox": tuple(row.bbox) if row.bbox else None,
            }
        )

    @staticmethod
    def _from_evidence(evidence: Evidence) -> EvidenceRow:
        return EvidenceRow(**evidence.model_dump())


def build_repository(data_root: Path, db_url: str | None) -> DocumentRepository | SqlDocumentRepository:
    """Factory used by the API lifespan."""
    if db_url and _SQLALCHEMY_AVAILABLE:
        try:
            return SqlDocumentRepository(db_url)
        except Exception:
            return DocumentRepository(Path(data_root))
    return DocumentRepository(Path(data_root))
