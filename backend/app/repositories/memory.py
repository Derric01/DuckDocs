"""Local repository used by the API's bootstrap path.

The repository boundary is intentionally small so it can be replaced by the
PostgreSQL/SQLAlchemy implementation without changing routers or services.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from app.domain.models import Document, Evidence, IngestJob, utc_now
from app.services.chunking import ChunkCandidate


class DocumentRepository:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.state_path = data_root / "state.json"
        self.documents: dict[str, Document] = {}
        self.jobs: dict[str, IngestJob] = {}
        self.evidence: dict[str, Evidence] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return

        documents = raw.get("documents", [])
        jobs = raw.get("jobs", [])
        evidence = raw.get("evidence", [])
        try:
            if isinstance(documents, list):
                self.documents = {
                    document.id: document
                    for item in documents
                    if isinstance(item, dict)
                    for document in [Document.model_validate(item)]
                }
            if isinstance(jobs, list):
                self.jobs = {
                    job.id: job
                    for item in jobs
                    if isinstance(item, dict)
                    for job in [IngestJob.model_validate(item)]
                }
            if isinstance(evidence, list):
                self.evidence = {
                    evidence_unit.id: evidence_unit
                    for item in evidence
                    if isinstance(item, dict)
                    for evidence_unit in [Evidence.model_validate(item)]
                }
        except ValidationError:
            self.documents = {}
            self.jobs = {}
            self.evidence = {}

    def _persist(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "documents": [document.model_dump(mode="json") for document in self.documents.values()],
            "jobs": [job.model_dump(mode="json") for job in self.jobs.values()],
            "evidence": [evidence.model_dump(mode="json") for evidence in self.evidence.values()],
            "updated_at": utc_now().isoformat(),
        }
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def list_documents(self) -> list[Document]:
        return list(self.documents.values())

    def get_document(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)

    def add_document(self, document: Document, job: IngestJob) -> None:
        self.documents[document.id] = document
        self.jobs[job.id] = job
        self._persist()

    def index_document_chunks(
        self, document_id: str, chunks: list[ChunkCandidate], ocr_engine: str | None = None
    ) -> int:
        document = self.documents.get(document_id)
        if document is None:
            return 0

        for evidence_id, evidence in list(self.evidence.items()):
            if evidence.document_id == document_id:
                del self.evidence[evidence_id]

        for index, chunk in enumerate(chunks, start=1):
            evidence_id = f"ev_{document_id.removeprefix('doc_')}_{index:04d}"
            self.evidence[evidence_id] = Evidence(
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
        self._persist()
        return len(chunks)

    def get_job(self, job_id: str) -> IngestJob | None:
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, **changes: object) -> IngestJob | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={**changes, "updated_at": utc_now()})
        self.jobs[job_id] = updated
        self._persist()
        return updated

    def update_document(self, document_id: str, **changes: object) -> Document | None:
        document = self.documents.get(document_id)
        if document is None:
            return None
        updated = document.model_copy(update={**changes, "updated_at": utc_now()})
        self.documents[document_id] = updated
        self._persist()
        return updated

    def search_evidence(self, query: str, limit: int) -> list[Evidence]:
        terms = {term for term in query.lower().split() if len(term) > 2}
        if not terms:
            return []
        ranked = sorted(self.evidence.values(), key=lambda item: self._score(item, terms), reverse=True)
        return [
            item
            for item in ranked
            if any(
                term in item.snippet.lower()
                or term in item.section.lower()
                or term in item.document_name.lower()
                for term in terms
            )
        ][:limit]

    def all_evidence(self) -> Iterable[Evidence]:
        return self.evidence.values()

    @staticmethod
    def _score(evidence: Evidence, terms: set[str]) -> int:
        haystack = f"{evidence.document_name} {evidence.section} {evidence.snippet}".lower()
        return sum(2 if term in evidence.snippet.lower() else int(term in haystack) for term in terms)
