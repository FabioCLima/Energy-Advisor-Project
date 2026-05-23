"""Tests for energy_advisor.tools.energy_data — query tools used by the ReAct agent."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from energy_advisor.services.database import DatabaseManager
from energy_advisor.tools.energy_data import (
    get_recent_energy_summary,
    query_energy_usage,
    query_solar_generation,
)


@pytest.fixture(autouse=True)
def patch_db_path(tmp_path, monkeypatch):
    """Point the tools at a fresh temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", db_path)

    # The tool caches the DatabaseManager via lru_cache — clear it between tests
    from energy_advisor.tools.energy_data import _get_db
    _get_db.cache_clear()

    db = DatabaseManager(db_path=db_path)
    db.create_tables()
    return db


@pytest.fixture()
def db(patch_db_path) -> DatabaseManager:
    return patch_db_path


# ── query_energy_usage ────────────────────────────────────────────────


def test_query_usage_empty_range(db):
    result = query_energy_usage.invoke({"start_date": "2025-01-01", "end_date": "2025-01-31"})
    assert result["total_consumption_kwh"] == 0.0
    assert result["device_breakdown"] == []


def test_query_usage_aggregates_by_device(db):
    ts = datetime(2025, 6, 15, 10, 0)
    db.add_usage_record(ts, 1.0, device_name="AC", device_type="ac", cost_brl=0.65)
    db.add_usage_record(ts, 2.0, device_name="AC", device_type="ac", cost_brl=1.31)
    result = query_energy_usage.invoke({"start_date": "2025-06-15", "end_date": "2025-06-15"})
    assert result["total_consumption_kwh"] == pytest.approx(3.0)
    assert len(result["device_breakdown"]) == 1
    assert result["device_breakdown"][0]["device_name"] == "AC"
    assert result["device_breakdown"][0]["consumption_kwh"] == pytest.approx(3.0)


def test_query_usage_device_name_filter(db):
    ts = datetime(2025, 6, 15, 10, 0)
    db.add_usage_record(ts, 1.0, device_name="Fridge", cost_brl=0.50)
    db.add_usage_record(ts, 3.0, device_name="Tesla Model 3", cost_brl=1.60)
    result = query_energy_usage.invoke({
        "start_date": "2025-06-15",
        "end_date": "2025-06-15",
        "device_name": "Tesla Model 3",
    })
    assert len(result["device_breakdown"]) == 1
    assert result["device_breakdown"][0]["device_name"] == "Tesla Model 3"


def test_query_usage_pattern_filter(db):
    ts = datetime(2025, 6, 15, 10, 0)
    db.add_usage_record(ts, 1.0, device_name="Fridge", usage_pattern="always_on")
    db.add_usage_record(ts, 3.0, device_name="EV", usage_pattern="scheduled")
    result = query_energy_usage.invoke({
        "start_date": "2025-06-15",
        "end_date": "2025-06-15",
        "usage_pattern": "always_on",
    })
    assert len(result["device_breakdown"]) == 1
    assert result["device_breakdown"][0]["usage_pattern"] == "always_on"


def test_query_usage_invalid_date_format(db):
    result = query_energy_usage.invoke({"start_date": "15/06/2025", "end_date": "2025-06-15"})
    assert "error" in result


def test_query_usage_sorted_by_cost_descending(db):
    ts = datetime(2025, 6, 15, 10, 0)
    db.add_usage_record(ts, 0.5, device_name="Light", cost_brl=0.10)
    db.add_usage_record(ts, 5.0, device_name="EV", cost_brl=3.20)
    db.add_usage_record(ts, 2.0, device_name="AC", cost_brl=1.30)
    result = query_energy_usage.invoke({"start_date": "2025-06-15", "end_date": "2025-06-15"})
    costs = [d["cost_brl"] for d in result["device_breakdown"]]
    assert costs == sorted(costs, reverse=True)


# ── query_solar_generation ────────────────────────────────────────────


def test_query_solar_empty(db):
    result = query_solar_generation.invoke({"start_date": "2025-01-01", "end_date": "2025-01-31"})
    assert result["total_generation_kwh"] == 0.0
    assert result["records"] == []


def test_query_solar_aggregates(db):
    ts = datetime(2025, 6, 21, 12, 0)
    db.add_generation_record(ts, 4.5, weather_condition="sunny", temperature_c=28.0)
    db.add_generation_record(ts + timedelta(hours=1), 3.0, weather_condition="sunny")
    result = query_solar_generation.invoke({"start_date": "2025-06-21", "end_date": "2025-06-21"})
    assert result["total_generation_kwh"] == pytest.approx(7.5)
    assert result["total_records"] == 2


def test_query_solar_invalid_date(db):
    result = query_solar_generation.invoke({"start_date": "bad-date", "end_date": "2025-06-21"})
    assert "error" in result


# ── get_recent_energy_summary ─────────────────────────────────────────


def test_recent_summary_empty_db(db):
    result = get_recent_energy_summary.invoke({"hours": 24})
    assert result["usage"]["total_consumption_kwh"] == 0.0
    assert result["generation"]["total_generation_kwh"] == 0.0


def test_recent_summary_only_includes_recent(db):
    now = datetime.now()
    db.add_usage_record(now - timedelta(hours=2), 1.0, cost_brl=0.65)
    db.add_usage_record(now - timedelta(hours=30), 5.0, cost_brl=3.28)
    result = get_recent_energy_summary.invoke({"hours": 24})
    assert result["usage"]["total_consumption_kwh"] == pytest.approx(1.0)


def test_recent_summary_invalid_hours(db):
    result = get_recent_energy_summary.invoke({"hours": 0})
    assert "error" in result
    result2 = get_recent_energy_summary.invoke({"hours": 9000})
    assert "error" in result2


def test_recent_summary_device_breakdown(db):
    now = datetime.now()
    db.add_usage_record(now - timedelta(hours=1), 1.0, device_type="ac", cost_brl=0.65)
    db.add_usage_record(now - timedelta(hours=1), 2.0, device_type="ev", cost_brl=1.31)
    result = get_recent_energy_summary.invoke({"hours": 24})
    breakdown = result["usage"]["device_breakdown"]
    assert "ac" in breakdown
    assert "ev" in breakdown
    assert breakdown["ac"]["consumption_kwh"] == pytest.approx(1.0)
