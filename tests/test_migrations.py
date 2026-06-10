"""Smoke test: the Alembic baseline produces the schema the app expects."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

alembic_command = pytest.importorskip("alembic.command")
from alembic.config import Config  # noqa: E402


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
