"""Baseline schema — energy_usage and solar_generation.

Mirrors the SQLAlchemy models in energy_advisor/services/database.py at the
moment migrations were introduced. Databases created earlier by
Base.metadata.create_all can adopt migrations with `alembic stamp head`.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "energy_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("consumption_kwh", sa.Float(), nullable=False),
        sa.Column("device_type", sa.String(length=50), nullable=True),
        sa.Column("device_name", sa.String(length=100), nullable=True),
        sa.Column("usage_pattern", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=50), nullable=True),
        sa.Column("cost_brl", sa.Float(), nullable=True),
    )
    op.create_table(
        "solar_generation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("generation_kwh", sa.Float(), nullable=False),
        sa.Column("weather_condition", sa.String(length=50), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("solar_irradiance", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("solar_generation")
    op.drop_table("energy_usage")
