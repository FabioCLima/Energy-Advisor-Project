"""Alembic environment — wired to the application's models and settings.

The migration URL comes from ENERGY_ADVISOR_DB_PATH (same env var the app
uses), so `alembic upgrade head` always targets the database the app would.
"""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from energy_advisor.services.database import Base

target_metadata = Base.metadata


def _database_url() -> str:
    db_path = os.environ.get("ENERGY_ADVISOR_DB_PATH", "data/energy_data.db")
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
