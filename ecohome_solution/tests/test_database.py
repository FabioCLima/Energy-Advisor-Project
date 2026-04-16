"""Tests for energy_advisor.services.database.DatabaseManager."""
from __future__ import annotations

from datetime import datetime, timedelta

from energy_advisor.services.database import DatabaseManager


def test_create_tables(db: DatabaseManager):
    """Tables should exist after create_tables is called."""
    # If tables exist, these queries return 0 (not error)
    assert db.count_usage_records() == 0
    assert db.count_generation_records() == 0


def test_add_and_query_usage(db: DatabaseManager):
    ts = datetime(2025, 1, 15, 14, 0, 0)
    db.add_usage_record(
        timestamp=ts,
        consumption_kwh=2.5,
        device_type="EV",
        device_name="Tesla Model 3",
        cost_usd=0.30,
    )
    records = db.get_usage_by_date_range(
        datetime(2025, 1, 15), datetime(2025, 1, 16)
    )
    assert len(records) == 1
    assert records[0].consumption_kwh == 2.5
    assert records[0].device_type == "EV"


def test_add_and_query_solar(db: DatabaseManager):
    ts = datetime(2025, 6, 21, 12, 0, 0)
    db.add_generation_record(
        timestamp=ts,
        generation_kwh=4.8,
        weather_condition="sunny",
        temperature_c=28.0,
        solar_irradiance=850.0,
    )
    records = db.get_generation_by_date_range(
        datetime(2025, 6, 21), datetime(2025, 6, 22)
    )
    assert len(records) == 1
    assert records[0].generation_kwh == 4.8
    assert records[0].weather_condition == "sunny"


def test_date_range_filter(db: DatabaseManager):
    """Only records within the requested range should be returned."""
    for day in range(1, 6):
        db.add_usage_record(
            timestamp=datetime(2025, 3, day, 10, 0),
            consumption_kwh=1.0,
        )
    results = db.get_usage_by_date_range(
        datetime(2025, 3, 2), datetime(2025, 3, 4, 23, 59, 59)
    )
    assert len(results) == 3  # days 2, 3, 4 — end_date must cover the 10:00 record


def test_count_records(db: DatabaseManager):
    assert db.count_usage_records() == 0
    db.add_usage_record(datetime(2025, 1, 1, 8), 1.0)
    db.add_usage_record(datetime(2025, 1, 1, 9), 1.5)
    assert db.count_usage_records() == 2


def test_empty_range_returns_empty_list(db: DatabaseManager):
    results = db.get_usage_by_date_range(
        datetime(2020, 1, 1), datetime(2020, 1, 31)
    )
    assert results == []


def test_recent_usage_window(db: DatabaseManager):
    now = datetime.now()
    db.add_usage_record(timestamp=now - timedelta(hours=2), consumption_kwh=1.0)
    db.add_usage_record(timestamp=now - timedelta(hours=30), consumption_kwh=2.0)
    recent = db.get_recent_usage(hours=24)
    assert len(recent) == 1
    assert recent[0].consumption_kwh == 1.0
