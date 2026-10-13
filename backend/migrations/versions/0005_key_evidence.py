"""Nullable key-path evidence; re-ingest JSON/YAML/XML to populate it."""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("key_value", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "key_value")
