from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from loguru import logger

try:
    from joblib import dump, load  # type: ignore
    from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore
except Exception:  # pragma: no cover
    dump = load = None  # type: ignore
    HistGradientBoostingRegressor = None  # type: ignore

from .database import DatabaseManager
from .usage_forecasting import UsageForecastParams, _floor_to_hour, load_hourly_usage_series


@dataclass(frozen=True)
class SklearnForecasterConfig:
    lags: tuple[int, ...] = (1, 2, 3, 24, 48, 72, 168)
    max_iter: int = 250
    learning_rate: float = 0.08
    max_depth: int = 4
    random_state: int = 42


def _cyclical(value: int, period: int) -> tuple[float, float]:
    angle = 2.0 * np.pi * (value % period) / period
    return float(np.sin(angle)), float(np.cos(angle))


def _build_feature_row(history: list[float], ts: datetime, lags: tuple[int, ...]) -> list[float]:
    feats: list[float] = []
    for lag in lags:
        feats.append(history[-lag])

    h_sin, h_cos = _cyclical(ts.hour, 24)
    dow_sin, dow_cos = _cyclical(ts.weekday(), 7)
    feats.extend([h_sin, h_cos, dow_sin, dow_cos])

    return feats


def _feature_names(lags: tuple[int, ...]) -> list[str]:
    names = [f"lag_{lag}" for lag in lags]
    names += ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]
    return names


def train_usage_forecaster(
    series: pd.Series,
    config: SklearnForecasterConfig,
) -> dict:
    """Train a local autoregressive regressor on an hourly consumption series.

    The model predicts 1-step ahead. Multi-step forecasts are generated recursively
    by feeding predictions back into the lag history.
    """
    if HistGradientBoostingRegressor is None:
        raise RuntimeError("scikit-learn is not installed")

    if series.empty:
        raise ValueError("series is empty")

    max_lag = max(config.lags)
    if len(series) <= max_lag + 24:
        raise ValueError("not enough history to train: need > max_lag + 24 hours")

    values = series.values.astype(float)
    index = series.index

    X: list[list[float]] = []
    y: list[float] = []

    # Point-in-time correctness: row at t uses only values < t.
    for i in range(max_lag, len(values)):
        ts = index[i].to_pydatetime()
        history = list(values[:i])
        X.append(_build_feature_row(history, ts, config.lags))
        y.append(float(values[i]))

    model = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_depth=config.max_depth,
        random_state=config.random_state,
        early_stopping=False,
    )
    model.fit(X, y)

    return {
        "type": "sklearn_hgb",
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "lags": list(config.lags),
        "feature_names": _feature_names(config.lags),
        "model": model,
    }


def save_forecaster(artifact: dict, path: str) -> None:
    if dump is None:
        raise RuntimeError("joblib is not installed")

    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    dump(artifact, path)


def load_forecaster(path: str) -> dict:
    if load is None:
        raise RuntimeError("joblib is not installed")

    return load(path)


def recursive_forecast(
    series: pd.Series,
    artifact: dict,
    params: UsageForecastParams,
    reference_time: datetime | None = None,
) -> list[dict]:
    if series.empty:
        return []

    model = artifact.get("model")
    lags = tuple(int(x) for x in artifact.get("lags", []))
    if not lags:
        raise ValueError("artifact missing lags")

    ref = _floor_to_hour(reference_time or datetime.now())
    history_series = series[series.index < ref]
    if history_series.empty:
        return []

    history: list[float] = history_series.values.astype(float).tolist()
    max_lag = max(lags)
    if len(history) < max_lag:
        raise ValueError("not enough history for forecast")

    points: list[dict] = []
    for step in range(params.horizon_hours):
        ts = ref + timedelta(hours=step)
        feats = _build_feature_row(history, ts, lags)
        yhat = float(model.predict([feats])[0])
        yhat = max(0.0, yhat)
        history.append(yhat)
        points.append({"timestamp": ts.isoformat(timespec="minutes"), "predicted_kwh": round(yhat, 4)})

    return points


def forecast_energy_usage_ml(
    db_path: str,
    model_path: str,
    device_type: str | None,
    params: UsageForecastParams,
    reference_time: datetime | None = None,
) -> dict:
    db = DatabaseManager(db_path=db_path)
    series = load_hourly_usage_series(db, device_type=device_type)
    artifact = load_forecaster(model_path)
    points = recursive_forecast(series, artifact=artifact, params=params, reference_time=reference_time)

    logger.debug(
        "forecast_energy_usage_ml | device_type={} horizon_hours={} points={} model_path={}",
        device_type,
        params.horizon_hours,
        len(points),
        model_path,
    )

    return {
        "device_type": device_type,
        "method": "sklearn_hgb",
        "horizon_hours": params.horizon_hours,
        "points": points,
        "total_predicted_kwh": round(sum(p["predicted_kwh"] for p in points), 4),
        "model_path": model_path,
    }
