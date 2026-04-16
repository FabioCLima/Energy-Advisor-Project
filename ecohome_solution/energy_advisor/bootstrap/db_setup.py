"""
Bootstrap step 1: Database initialisation.

Creates the SQLite database and all tables if they do not already exist.

Usage:
    python -m energy_advisor.bootstrap.db_setup
"""
from __future__ import annotations

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager


def setup_database(settings: Settings | None = None) -> DatabaseManager:
    """Create the SQLite database and all ORM tables.

    Idempotent — safe to run multiple times.

    Args:
        settings: Optional Settings instance. Uses defaults when omitted.

    Returns:
        Initialised DatabaseManager bound to the configured db_path.
    """
    settings = settings or Settings()
    logger.info("Setting up database at {}", settings.db_path)
    db = DatabaseManager(db_path=settings.db_path)
    db.create_tables()
    logger.info("Database ready.")
    return db


if __name__ == "__main__":
    setup_database()
