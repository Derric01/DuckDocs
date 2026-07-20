"""Optional PostgreSQL repository selected via DUCKDOCS_DB_URL."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.domain.models import Document, Evidence, IngestJob, utc_now

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

    def index_document_text(self, document_id: str, text: str) -> int:
        document = self.get_document(document_id)
        if document is None:
            return 0
        normalized = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")).strip()
        if not normalized:
            return 0
        with self.SessionLocal() as session:
            existing = session.scalars(select(EvidenceRow).where(EvidenceRow.document_id == document_id)).all()
            for row in existing:
                session.delete(row)
            chunks = self._chunk_text(normalized)
            for index, (line_start, line_end, snippet) in enumerate(chunks, start=1):
                evidence_id = f"ev_{document_id.removeprefix('doc_')}_{index:02d}"
                evidence = Evidence(
                    id=evidence_id,
                    document_id=document_id,
                    document_name=document.name,
                    section="Imported content",
                    page=max(1, (line_start - 1) // 45 + 1),
                    line_start=line_start,
                    line_end=line_end,
                    snippet=snippet,
                    retrieval_score=0.74,
                    relevance="Medium",
                )
                session.merge(self._from_evidence(evidence))
                self.evidence[evidence_id] = evidence
            session.commit()
        for evidence_id, evidence in list(self.evidence.items()):
            if evidence.document_id == document_id and evidence_id not in {
                f"ev_{document_id.removeprefix('doc_')}_{index:02d}" for index in range(1, len(chunks) + 1)
            }:
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
    def _chunk_text(text: str, max_chars: int = 900) -> list[tuple[int, int, str]]:
        lines = [line.strip() for line in text.splitlines()]
        chunks: list[tuple[int, int, str]] = []
        current: list[str] = []
        start_line = 1
        current_length = 0
        for index, line in enumerate(lines, start=1):
            if not line and current:
                chunks.append((start_line, index - 1, " ".join(current).strip()))
                current = []
                current_length = 0
                start_line = index + 1
                continue
            if not line:
                start_line = index + 1
                continue
            if current and current_length + len(line) + 1 > max_chars:
                chunks.append((start_line, index - 1, " ".join(current).strip()))
                current = [line]
                current_length = len(line)
                start_line = index
                continue
            current.append(line)
            current_length += len(line) + 1
        if current:
            chunks.append((start_line, len(lines), " ".join(current).strip()))
        return [chunk for chunk in chunks if chunk[2]][:12]

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
            }
        )

    @staticmethod
    def _from_evidence(evidence: Evidence) -> EvidenceRow:
        return EvidenceRow(**evidence.model_dump())


def build_repository(data_root, db_url: str | None):
    """Factory used by the API lifespan."""
    from pathlib import Path

    from app.repositories.memory import DocumentRepository

    if db_url and _SQLALCHEMY_AVAILABLE:
        try:
            return SqlDocumentRepository(db_url)
        except Exception:
            return DocumentRepository(Path(data_root))
    return DocumentRepository(Path(data_root))
