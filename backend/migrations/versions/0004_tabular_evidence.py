"""Nullable structured row metadata; legacy evidence survives until re-ingestion."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("table_row", sa.JSON(), nullable=True))
    op.add_column("evidence", sa.Column("file_type", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "file_type")
    op.drop_column("evidence", "table_row")
