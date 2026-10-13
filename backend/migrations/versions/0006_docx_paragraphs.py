"""Store page-local DOCX paragraph ordinals; re-ingest DOCX to populate them."""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("paragraph_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "paragraph_number")
