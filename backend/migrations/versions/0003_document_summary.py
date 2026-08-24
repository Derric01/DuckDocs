"""Store the ingest-time document summary.

`summary_method` records how the text was produced (extractive vs abstractive)
so the UI can label it honestly instead of implying a model wrote it.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("summary_method", sa.String(16), nullable=True))
    op.add_column("documents", sa.Column("summary_provider", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "summary_provider")
    op.drop_column("documents", "summary_method")
    op.drop_column("documents", "summary")
