"""Smoke test: the Alembic baseline produces the schema the app expects."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

alembic_command = pytest.importorskip("alembic.command")
from alembic.config import Config  # noqa: E402

# ── E-3: bootstrap provisions schema via migrations ──────────────────

def test_setup_database_provisions_via_alembic(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "bootstrapped.db"
    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", str(db_path))
    from energy_advisor.bootstrap.db_setup import setup_database
    from energy_advisor.config import Settings

    setup_database(Settings())

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    tables = set(inspector.get_table_names())
    assert {"energy_usage", "solar_generation", "alembic_version"} <= tables


def test_setup_database_adopts_pre_migration_db_with_stamp(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", str(db_path))
    from energy_advisor.bootstrap.db_setup import setup_database
    from energy_advisor.config import Settings
    from energy_advisor.services.database import DatabaseManager

    # Legacy database: schema from ORM create_all, no migration bookkeeping.
    DatabaseManager(db_path=str(db_path)).create_tables()

    setup_database(Settings())  # must not raise "table already exists"

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    assert "alembic_version" in inspector.get_table_names()


def test_alembic_upgrade_head_creates_app_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", str(db_path))
    config = Config("alembic.ini")

    alembic_command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    tables = set(inspector.get_table_names())
    assert {"energy_usage", "solar_generation"} <= tables

    usage_columns = {c["name"] for c in inspector.get_columns("energy_usage")}
    assert {"timestamp", "consumption_kwh", "device_name", "cost_brl"} <= usage_columns
