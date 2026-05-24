"""Tests for energy_advisor.services.optimizer."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.optimizer import Recommendation, generate_recommendations


def _seed_usage(db: DatabaseManager, device_type: str, hours: int = 24 * 7) -> None:
    start = datetime(2026, 5, 1, 0, 0, 0)
    for h in range(hours):
        ts = start + timedelta(hours=h)
        db.add_usage_record(
            timestamp=ts,
            consumption_kwh=0.3,
            device_type=device_type,
            device_name=device_type,
        )


def test_generate_recommendations_returns_list(tmp_db_path: str, db: DatabaseManager) -> None:
    for dtype in ("ev", "hvac", "appliance"):
        _seed_usage(db, dtype)

    recs = generate_recommendations(db_path=tmp_db_path)

    assert isinstance(recs, list)
    assert len(recs) > 0
    assert all(isinstance(r, Recommendation) for r in recs)


def test_recommendations_are_ranked(tmp_db_path: str, db: DatabaseManager) -> None:
    for dtype in ("ev", "hvac", "appliance"):
        _seed_usage(db, dtype)

    recs = generate_recommendations(db_path=tmp_db_path)

    ranks = [r.rank for r in recs]
    assert ranks == list(range(1, len(recs) + 1))

    savings = [r.savings_30d_brl for r in recs]
    assert savings == sorted(savings, reverse=True)


def test_savings_are_non_negative(tmp_db_path: str, db: DatabaseManager) -> None:
    for dtype in ("ev", "hvac", "appliance"):
        _seed_usage(db, dtype)

    recs = generate_recommendations(db_path=tmp_db_path)

    for r in recs:
        assert r.savings_7d_brl >= 0.0
        assert r.savings_30d_brl >= 0.0
        assert r.savings_90d_brl >= 0.0


def test_confidence_values_are_valid(tmp_db_path: str, db: DatabaseManager) -> None:
    for dtype in ("ev", "hvac", "appliance"):
        _seed_usage(db, dtype)

    recs = generate_recommendations(db_path=tmp_db_path)

    valid = {"high", "medium", "low"}
    for r in recs:
        assert r.confidence in valid


def test_horizon_days_clamp(tmp_db_path: str, db: DatabaseManager) -> None:
    _seed_usage(db, "ev")

    recs_7  = generate_recommendations(db_path=tmp_db_path, horizon_days=7)
    recs_30 = generate_recommendations(db_path=tmp_db_path, horizon_days=30)

    ev_7  = next((r for r in recs_7  if r.device_type == "ev"), None)
    ev_30 = next((r for r in recs_30 if r.device_type == "ev"), None)

    if ev_7 and ev_30:
        assert ev_7.savings_7d_brl == ev_30.savings_7d_brl


def test_empty_db_returns_empty_list(tmp_db_path: str, db: DatabaseManager) -> None:
    recs = generate_recommendations(db_path=tmp_db_path)
    assert recs == []
