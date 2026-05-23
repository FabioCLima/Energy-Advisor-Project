from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.usage_forecasting import (
    UsageForecastParams,
    forecast_energy_usage,
    load_hourly_usage_series,
    seasonal_naive_usage_forecast,
)


def _add_hourly_usage(db: DatabaseManager, start: datetime, hours: int, kwh: float, device_type: str) -> None:
    t = start
    for _ in range(hours):
        db.add_usage_record(timestamp=t, consumption_kwh=kwh, device_type=device_type, device_name=device_type)
        t += timedelta(hours=1)


def test_load_hourly_usage_series_fills_gaps(db: DatabaseManager) -> None:
    start = datetime(2026, 5, 1, 0, 0, 0)
    db.add_usage_record(timestamp=start, consumption_kwh=1.0, device_type="hvac")
    db.add_usage_record(timestamp=start + timedelta(hours=2), consumption_kwh=2.0, device_type="hvac")

    series = load_hourly_usage_series(db, device_type="hvac")
    assert isinstance(series, pd.Series)
    assert len(series) == 3
    assert float(series.iloc[0]) == 1.0
    assert float(series.iloc[1]) == 0.0  # gap filled
    assert float(series.iloc[2]) == 2.0


def test_seasonal_naive_returns_horizon(db: DatabaseManager) -> None:
    # Continuous history: 14 days hourly = 336 points
    start = datetime(2026, 5, 1, 0, 0, 0)
    _add_hourly_usage(db, start=start, hours=24 * 14, kwh=0.5, device_type="ev")

    series = load_hourly_usage_series(db, device_type="ev")
    params = UsageForecastParams(horizon_hours=24, lookback_weeks=2)
    ref = start + timedelta(days=14)

    points = seasonal_naive_usage_forecast(series, params=params, reference_time=ref)
    assert len(points) == 24
    assert all("timestamp" in p and "predicted_kwh" in p for p in points)
    assert all(p["predicted_kwh"] >= 0.0 for p in points)


def test_forecast_energy_usage_payload_shape(tmp_db_path: str, db: DatabaseManager) -> None:
    start = datetime(2026, 5, 1, 0, 0, 0)
    _add_hourly_usage(db, start=start, hours=24 * 7, kwh=0.2, device_type="lighting")

    payload = forecast_energy_usage(
        db_path=tmp_db_path,
        device_type="lighting",
        params=UsageForecastParams(horizon_hours=24),
        reference_time=start + timedelta(days=7),
    )

    assert payload["method"] == "seasonal_naive"
    assert payload["horizon_hours"] == 24
    assert len(payload["points"]) == 24
    assert payload["total_predicted_kwh"] >= 0.0
