"""Drift report runner tests — DB windows → report JSON."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from energy_advisor.config import Settings
from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.drift_report import build_drift_report


def _seed(db: DatabaseManager, *, baseline_kwh: float, current_kwh: float) -> None:
    now = datetime.now()
    for days_ago in range(1, 61):
        # +1h margin keeps each record safely inside its window even though
        # build_drift_report computes its own `now` microseconds later.
        ts = now - timedelta(days=days_ago) + timedelta(hours=1)
        kwh = current_kwh if days_ago <= 30 else baseline_kwh
        db.add_usage_record(timestamp=ts, consumption_kwh=kwh, device_name="PC")
        db.add_generation_record(timestamp=ts, generation_kwh=kwh / 2)


@pytest.fixture()
def drift_settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", str(tmp_path / "drift.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-placeholder")
    return Settings()


def test_detects_mean_shift_between_windows(drift_settings) -> None:
    db = DatabaseManager(db_path=drift_settings.db_path)
    db.create_tables()
    _seed(db, baseline_kwh=1.0, current_kwh=2.0)  # +100% » 25% threshold

    report = build_drift_report(drift_settings)

    assert report["drift_detected"] is True
    usage = report["series"]["usage"]["feature_results"][0]
    assert usage["drift_detected"] is True
    assert usage["relative_change"] == pytest.approx(1.0, abs=0.05)


def test_no_drift_when_windows_match(drift_settings) -> None:
    db = DatabaseManager(db_path=drift_settings.db_path)
    db.create_tables()
    _seed(db, baseline_kwh=1.0, current_kwh=1.0)

    report = build_drift_report(drift_settings)

    assert report["drift_detected"] is False
    assert report["series"]["usage"]["rows_baseline"] == 30
    assert report["series"]["usage"]["rows_current"] == 30


def test_empty_window_raises_instead_of_silent_pass(drift_settings) -> None:
    db = DatabaseManager(db_path=drift_settings.db_path)
    db.create_tables()  # no rows at all

    with pytest.raises(ValueError, match="Empty usage window"):
        build_drift_report(drift_settings)
