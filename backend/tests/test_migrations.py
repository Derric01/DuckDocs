"""Schema migrations run against a real database.

SQLite stands in for Postgres here. The revisions use only portable DDL, and
running them for real is what catches an ordering mistake -- an import-only
test would not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.repositories.migrations import BASELINE_REVISION, upgrade_database
from app.repositories.sql import SqlDocumentRepository

EVIDENCE_PROVENANCE_COLUMNS = {"fidelity_tier", "ocr_confidence", "ocr_engine", "bbox"}
SUMMARY_COLUMNS = {"summary", "summary_method", "summary_provider"}


def _columns(engine: object, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}  # type: ignore[arg-type]


def test_fresh_database_migrates_to_head(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    engine = create_engine(url)

    upgrade_database(engine, url)

    tables = set(inspect(engine).get_table_names())
    assert {"documents", "ingest_jobs", "evidence", "provider_configs", "alembic_version"} <= tables
    assert EVIDENCE_PROVENANCE_COLUMNS <= _columns(engine, "evidence")
    assert SUMMARY_COLUMNS <= _columns(engine, "documents")


def test_head_is_recorded_so_a_second_run_is_a_no_op(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'twice.db'}"
    engine = create_engine(url)
    upgrade_database(engine, url)
    with engine.connect() as connection:
        first = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    upgrade_database(engine, url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == first


def test_a_pre_alembic_database_is_adopted_and_upgraded(tmp_path: Path) -> None:
    """The case create_all silently got wrong: tables exist, columns are missing."""
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)

    # The shape that shipped before migrations existed, with one row in it.
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id VARCHAR(64) PRIMARY KEY, name VARCHAR(512), file_type VARCHAR(32),"
                "mime_type VARCHAR(128), size_bytes INTEGER, status VARCHAR(32),"
                "fidelity_tier VARCHAR(32), pages INTEGER, category VARCHAR(128),"
                "current_version_id VARCHAR(64), created_at TIMESTAMP, updated_at TIMESTAMP, tags JSON)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE evidence ("
                "id VARCHAR(64) PRIMARY KEY, document_id VARCHAR(64), document_name VARCHAR(512),"
                "section VARCHAR(256), page INTEGER, line_start INTEGER, line_end INTEGER,"
                "snippet TEXT, retrieval_score FLOAT, relevance VARCHAR(16),"
                "anchor_quality VARCHAR(32) DEFAULT 'line')"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE ingest_jobs ("
                "id VARCHAR(64) PRIMARY KEY, document_id VARCHAR(64), status VARCHAR(32),"
                "stage VARCHAR(32), progress_pct INTEGER, error JSON,"
                "created_at TIMESTAMP, updated_at TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE provider_configs ("
                "id VARCHAR(64) PRIMARY KEY, role VARCHAR(16), provider_type VARCHAR(32),"
                "model_name VARCHAR(128), base_url VARCHAR(512), api_key_ref VARCHAR(128),"
                "is_default BOOLEAN DEFAULT 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO documents (id, name, file_type, mime_type, size_bytes, status,"
                " fidelity_tier, pages, category, current_version_id, created_at, updated_at, tags)"
                " VALUES ('doc_legacy', 'old.pdf', 'pdf', 'application/pdf', 10, 'ready',"
                " 'structural', 2, 'Contracts', 'ver_1', '2026-01-01', '2026-01-01', '[]')"
            )
        )

    upgrade_database(engine, url)

    assert EVIDENCE_PROVENANCE_COLUMNS <= _columns(engine, "evidence")
    assert SUMMARY_COLUMNS <= _columns(engine, "documents")
    with engine.connect() as connection:
        # The existing row survives the upgrade rather than being dropped.
        assert connection.execute(text("SELECT name FROM documents")).scalar_one() == "old.pdf"
        # And it was adopted at the baseline, not re-created from scratch.
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != BASELINE_REVISION


def test_repository_opens_a_migrated_database(tmp_path: Path) -> None:
    """End to end: the repository's own startup path produces a usable schema."""
    url = f"sqlite:///{tmp_path / 'repo.db'}"
    repository = SqlDocumentRepository(url)

    assert repository.list_documents() == []
    assert "alembic_version" in inspect(repository.engine).get_table_names()


def test_repository_refuses_to_start_on_a_broken_populated_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running new code against an un-upgraded schema would corrupt silently."""
    url = f"sqlite:///{tmp_path / 'broken.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE documents (id VARCHAR(64) PRIMARY KEY)"))

    def _fail(*_: object, **__: object) -> None:
        raise RuntimeError("alembic exploded")

    monkeypatch.setattr("app.repositories.sql.upgrade_database", _fail)
    with pytest.raises(RuntimeError, match="alembic exploded"):
        SqlDocumentRepository(url)
