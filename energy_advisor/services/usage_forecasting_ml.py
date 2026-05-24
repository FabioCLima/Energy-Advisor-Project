from __future__ import annotations

import math
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
from .usage_forecasting import (
    UsageForecastParams,
    _floor_to_hour,
    load_hourly_usage_series,
    seasonal_naive_usage_forecast,
)


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


def _regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if not y_true:
        raise ValueError("metrics require at least one sample")

    errors = [abs(a - b) for a, b in zip(y_true, y_pred, strict=True)]
    squared = [(a - b) ** 2 for a, b in zip(y_true, y_pred, strict=True)]
    mae = sum(errors) / len(errors)
    rmse = math.sqrt(sum(squared) / len(squared))
    return {"mae": round(mae, 6), "rmse": round(rmse, 6)}


def _improvement_pct(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        return 0.0
    return round(((baseline - candidate) / baseline) * 100.0, 2)


def train_usage_forecaster(series: pd.Series, config: SklearnForecasterConfig) -> dict:
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


def evaluate_holdout_window(
    series: pd.Series,
    config: SklearnForecasterConfig,
    *,
    holdout_hours: int = 24 * 7,
    lookback_weeks: int = 8,
) -> dict:
    if series.empty:
        raise ValueError("series is empty")

    max_lag = max(config.lags)
    minimum_history = max_lag + holdout_hours + 24
    if len(series) <= minimum_history:
        raise ValueError(f"not enough history to evaluate: need > {minimum_history} hours")

    train_series = series.iloc[:-holdout_hours]
    holdout_series = series.iloc[-holdout_hours:]
    holdout_start = holdout_series.index.min().to_pydatetime()
    params = UsageForecastParams(horizon_hours=holdout_hours, lookback_weeks=lookback_weeks)

    eval_artifact = train_usage_forecaster(train_series, config=config)
    ml_points = recursive_forecast(
        train_series,
        artifact=eval_artifact,
        params=params,
        reference_time=holdout_start,
    )
    baseline_points = seasonal_naive_usage_forecast(
        train_series,
        params=params,
        reference_time=holdout_start,
    )

    y_true = [round(float(value), 4) for value in holdout_series.values.astype(float).tolist()]
    y_pred_ml = [float(point["predicted_kwh"]) for point in ml_points]
    y_pred_baseline = [float(point["predicted_kwh"]) for point in baseline_points]

    ml_metrics = _regression_metrics(y_true, y_pred_ml)
    baseline_metrics = _regression_metrics(y_true, y_pred_baseline)

    return {
        "holdout_hours": holdout_hours,
        "train_samples": int(len(train_series)),
        "test_samples": int(len(holdout_series)),
        "baseline_mae": baseline_metrics["mae"],
        "baseline_rmse": baseline_metrics["rmse"],
        "model_mae": ml_metrics["mae"],
        "model_rmse": ml_metrics["rmse"],
        "mae_improvement_pct": _improvement_pct(baseline_metrics["mae"], ml_metrics["mae"]),
        "rmse_improvement_pct": _improvement_pct(baseline_metrics["rmse"], ml_metrics["rmse"]),
        "evaluation_window_start": holdout_series.index.min().isoformat(timespec="minutes"),
        "evaluation_window_end": holdout_series.index.max().isoformat(timespec="minutes"),
    }


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

    payload = {
        "device_type": device_type,
        "method": "sklearn_hgb",
        "horizon_hours": params.horizon_hours,
        "points": points,
        "total_predicted_kwh": round(sum(p["predicted_kwh"] for p in points), 4),
        "model_path": model_path,
    }
    if artifact.get("validation") is not None:
        payload["validation"] = artifact["validation"]
    return payload
