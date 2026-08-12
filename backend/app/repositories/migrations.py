"""Schema migrations for the optional SQL repository.

`create_all` only ever creates missing tables -- it will not add a column to a
table that already exists, so a database written by an earlier build silently
kept the old shape and then failed at query time. Alembic makes the upgrade
explicit and ordered.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MIGRATIONS_ROOT = Path(__file__).resolve().parents[2]
"""The `backend/` directory, which holds alembic.ini and migrations/."""

# The revision matching the schema as it shipped before migrations existed.
# A database with tables but no alembic_version is stamped here, not rebuilt.
BASELINE_REVISION = "0001"


def _config(db_url: str) -> Any:
    from alembic.config import Config

    config = Config(str(MIGRATIONS_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_ROOT / "migrations"))
    # Escaped because Alembic runs the URL through ConfigParser interpolation,
    # where a bare '%' in a password would be read as a token.
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return config


def upgrade_database(engine: Any, db_url: str) -> None:
    """Bring the database to head, adopting a pre-Alembic database if needed."""
    from alembic import command
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    config = _config(db_url)

    if "alembic_version" not in tables and "documents" in tables:
        logger.info("Adopting an existing DuckDocs database at revision %s", BASELINE_REVISION)
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
