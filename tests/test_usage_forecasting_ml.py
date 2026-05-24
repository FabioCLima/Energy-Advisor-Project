from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from energy_advisor.config import Settings
from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.usage_forecasting import UsageForecastParams, load_hourly_usage_series


def _add_hourly_usage(db: DatabaseManager, start: datetime, hours: int, kwh: float, device_type: str) -> None:
    t = start
    for _ in range(hours):
        db.add_usage_record(timestamp=t, consumption_kwh=kwh, device_type=device_type, device_name=device_type)
        t += timedelta(hours=1)


@pytest.mark.skipif(
    os.environ.get("SKIP_SKLEARN") == "1",
    reason="Optional skip hook for environments without sklearn",
)
def test_train_save_load_and_recursive_forecast(tmp_path: Path, db: DatabaseManager) -> None:
    from energy_advisor.services.usage_forecasting_ml import (
        SklearnForecasterConfig,
        load_forecaster,
        recursive_forecast,
        save_forecaster,
        train_usage_forecaster,
    )

    start = datetime(2026, 5, 1, 0, 0, 0)
    _add_hourly_usage(db, start=start, hours=24 * 21, kwh=0.3, device_type="ev")

    series = load_hourly_usage_series(db, device_type="ev")
    artifact = train_usage_forecaster(series, config=SklearnForecasterConfig(max_iter=50))

    model_path = tmp_path / "usage_forecaster_ev.joblib"
    save_forecaster(artifact, str(model_path))
    loaded = load_forecaster(str(model_path))

    params = UsageForecastParams(horizon_hours=24)
    points = recursive_forecast(series, artifact=loaded, params=params, reference_time=start + timedelta(days=21))

    assert len(points) == 24
    assert all(p["predicted_kwh"] >= 0.0 for p in points)


def test_predict_energy_usage_uses_ml_when_model_exists(tmp_path: Path, tmp_db_path: str, db: DatabaseManager, monkeypatch) -> None:
    from energy_advisor.services.usage_forecasting_ml import (
        SklearnForecasterConfig,
        save_forecaster,
        train_usage_forecaster,
    )
    from energy_advisor.tools.forecast import predict_energy_usage

    start = datetime(2026, 5, 1, 0, 0, 0)
    _add_hourly_usage(db, start=start, hours=24 * 21, kwh=0.2, device_type="hvac")

    series = load_hourly_usage_series(db, device_type="hvac")
    artifact = train_usage_forecaster(series, config=SklearnForecasterConfig(max_iter=30))

    monkeypatch.setenv("ENERGY_ADVISOR_DB_PATH", tmp_db_path)
    monkeypatch.setenv("ENERGY_ADVISOR_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("ENERGY_ADVISOR_USAGE_FORECAST_MODE", "auto")

    settings = Settings()
    model_path = settings.usage_forecast_model_path("hvac")
    save_forecaster(artifact, model_path)

    result = predict_energy_usage.invoke({"device_type": "hvac", "horizon_hours": 24})
    assert result.get("method") == "sklearn_hgb"
    assert len(result.get("points", [])) == 24



def test_holdout_evaluation_persists_metrics(db: DatabaseManager) -> None:
    from energy_advisor.services.usage_forecasting_ml import (
        SklearnForecasterConfig,
        evaluate_holdout_window,
        train_usage_forecaster,
    )

    start = datetime(2026, 1, 1, 0, 0, 0)
    for hour in range(24 * 35):
        ts = start + timedelta(hours=hour)
        base = 0.2
        if ts.hour in {18, 19, 20}:
            base = 0.45
        if ts.weekday() >= 5:
            base += 0.05
        db.add_usage_record(
            timestamp=ts,
            consumption_kwh=base,
            device_type="appliance",
            device_name="appliance",
        )

    series = load_hourly_usage_series(db, device_type="appliance")
    validation = evaluate_holdout_window(
        series,
        SklearnForecasterConfig(max_iter=40),
        holdout_hours=24 * 7,
    )
    artifact = train_usage_forecaster(series, config=SklearnForecasterConfig(max_iter=40))
    artifact["validation"] = validation

    assert validation["test_samples"] == 24 * 7
    assert "model_rmse" in validation
    assert "baseline_rmse" in validation
    assert artifact["validation"]["holdout_hours"] == 24 * 7
