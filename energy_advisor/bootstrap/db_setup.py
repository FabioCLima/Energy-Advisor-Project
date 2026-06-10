"""
Bootstrap step 1: Database initialisation.

Provisions the schema by running Alembic migrations (`upgrade head`) — the
single source of truth for schema. `DatabaseManager.create_tables`
(ORM `create_all`) remains only for unit-test fixtures, where migration
history is irrelevant.

Usage:
    python -m energy_advisor.bootstrap.db_setup
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager


def _alembic_ini_path() -> Path:
    """Locate alembic.ini at the repo root (two levels above this package)."""
    candidate = Path(__file__).resolve().parents[2] / "alembic.ini"
    return candidate if candidate.exists() else Path("alembic.ini")


def run_migrations(settings: Settings) -> None:
    """Apply all pending Alembic migrations against the configured database.

    Databases created before migrations existed (ORM create_all, no
    alembic_version table) are adopted with `stamp head` instead — their
    schema already matches the baseline; only the bookkeeping is missing.
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import create_engine, inspect

    config = AlembicConfig(str(_alembic_ini_path()))
    # Hand the URL to migrations/env.py explicitly so programmatic runs always
    # target settings.db_path, regardless of process env vars.
    url = f"sqlite:///{settings.db_path}"
    config.attributes["db_url"] = url

    tables = set(inspect(create_engine(url)).get_table_names())
    if "energy_usage" in tables and "alembic_version" not in tables:
        logger.info("Pre-migration database detected — adopting with 'stamp head'.")
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")


def setup_database(settings: Settings | None = None) -> DatabaseManager:
    """Provision the database schema via Alembic and return a manager.

    Idempotent — `upgrade head` is a no-op when the schema is current.

    Args:
        settings: Optional Settings instance. Uses defaults when omitted.

    Returns:
        Initialised DatabaseManager bound to the configured db_path.
    """
    settings = settings or Settings()
    logger.info("Setting up database at {} (alembic upgrade head)", settings.db_path)
    db = DatabaseManager(db_path=settings.db_path)  # ensures parent dir exists
    run_migrations(settings)
    logger.info("Database ready.")
    return db


if __name__ == "__main__":
    setup_database()
