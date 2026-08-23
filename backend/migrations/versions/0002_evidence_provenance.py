"""Carry OCR provenance on each evidence unit.

Fidelity tier, OCR confidence, engine, and bounding box are stored per unit
rather than inferred at render time -- INVARIANT 1 in CLAUDE.md. Existing rows
default to `full_layout` with no OCR data, which is what they were.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence",
        sa.Column("fidelity_tier", sa.String(32), nullable=False, server_default="full_layout"),
    )
    op.add_column("evidence", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("evidence", sa.Column("ocr_engine", sa.String(32), nullable=True))
    op.add_column("evidence", sa.Column("bbox", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "bbox")
    op.drop_column("evidence", "ocr_engine")
    op.drop_column("evidence", "ocr_confidence")
    op.drop_column("evidence", "fidelity_tier")
