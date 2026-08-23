"""Initial schema.

Deliberately the shape that shipped before migrations existed, so a database
created by an earlier build can be stamped at this revision and then upgraded
instead of being rebuilt.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("fidelity_tier", sa.String(32), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("current_version_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
    )

    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingest_jobs_document_id", "ingest_jobs", ["document_id"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), nullable=False),
        sa.Column("document_name", sa.String(512), nullable=False),
        sa.Column("section", sa.String(256), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("relevance", sa.String(16), nullable=False),
        sa.Column("anchor_quality", sa.String(32), nullable=False, server_default="line"),
    )
    op.create_index("ix_evidence_document_id", "evidence", ["document_id"])

    op.create_table(
        "provider_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("api_key_ref", sa.String(128), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("provider_configs")
    op.drop_index("ix_evidence_document_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_ingest_jobs_document_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
    op.drop_table("documents")
