"""Shared pytest fixtures for the EcoHome Energy Advisor test suite."""
from __future__ import annotations

import os

import pytest
from energy_advisor.config import Settings
from energy_advisor.services.database import DatabaseManager


@pytest.fixture()
def tmp_db_path(tmp_path: pytest.TempPathFactory) -> str:
    """Return a path to a temporary SQLite database file."""
    return str(tmp_path / "test_energy.db")


@pytest.fixture()
def test_settings(tmp_db_path: str, tmp_path) -> Settings:
    """Settings instance pointing to temporary storage directories."""
    os.environ["ENERGY_ADVISOR_DB_PATH"] = tmp_db_path
    os.environ["ENERGY_ADVISOR_DOCS_DIR"] = str(tmp_path / "docs")
    os.environ["ENERGY_ADVISOR_VECTORSTORE_DIR"] = str(tmp_path / "vectorstore")
    os.environ.setdefault("OPENAI_API_KEY", "test-key-placeholder")
    return Settings()


@pytest.fixture()
def db(tmp_db_path: str) -> DatabaseManager:
    """Initialised DatabaseManager backed by a temporary file."""
    manager = DatabaseManager(db_path=tmp_db_path)
    manager.create_tables()
    return manager
