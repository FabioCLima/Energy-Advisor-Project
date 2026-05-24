"""Lightweight drift monitoring for energy usage and forecast quality."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class FeatureDriftResult:
    feature: str
    baseline_mean: float
    current_mean: float
    relative_change: float
    drift_detected: bool


@dataclass(frozen=True)
class ForecastDriftResult:
    target: str
    baseline_mae: float
    current_mae: float
    relative_change: float
    drift_detected: bool


@dataclass(frozen=True)
class DriftReport:
    feature_results: list[FeatureDriftResult]
    forecast_result: ForecastDriftResult | None
    drift_detected: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "drift_detected": self.drift_detected,
            "feature_results": [asdict(result) for result in self.feature_results],
            "forecast_result": asdict(self.forecast_result) if self.forecast_result else None,
        }


def _relative_change(baseline: float, current: float) -> float:
    if baseline == 0:
        return 0.0 if current == 0 else 1.0
    return (current - baseline) / abs(baseline)


def _mae(frame: pd.DataFrame, actual_col: str, prediction_col: str) -> float:
    errors = (frame[actual_col] - frame[prediction_col]).abs()
    return float(errors.mean()) if not errors.empty else 0.0


def monitor_energy_drift(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    *,
    feature_columns: Iterable[str],
    mean_shift_threshold: float = 0.25,
    actual_col: str | None = None,
    prediction_col: str | None = None,
    forecast_error_threshold: float = 0.30,
) -> DriftReport:
    """Compare baseline and current windows for data and forecast drift.

    The function is intentionally dataframe-based so it can receive data from SQLite,
    CSV exports, notebooks, Airflow jobs or future Evidently adapters.
    """
    feature_results: list[FeatureDriftResult] = []
    for feature in feature_columns:
        if feature not in baseline.columns or feature not in current.columns:
            raise ValueError(f"Feature column not found in both windows: {feature}")
        baseline_mean = float(baseline[feature].mean())
        current_mean = float(current[feature].mean())
        relative_change = _relative_change(baseline_mean, current_mean)
        feature_results.append(
            FeatureDriftResult(
                feature=feature,
                baseline_mean=round(baseline_mean, 6),
                current_mean=round(current_mean, 6),
                relative_change=round(relative_change, 6),
                drift_detected=abs(relative_change) > mean_shift_threshold,
            )
        )

    forecast_result: ForecastDriftResult | None = None
    if actual_col and prediction_col:
        for column in (actual_col, prediction_col):
            if column not in baseline.columns or column not in current.columns:
                raise ValueError(f"Forecast column not found in both windows: {column}")
        baseline_mae = _mae(baseline, actual_col, prediction_col)
        current_mae = _mae(current, actual_col, prediction_col)
        relative_change = _relative_change(baseline_mae, current_mae)
        forecast_result = ForecastDriftResult(
            target=actual_col,
            baseline_mae=round(baseline_mae, 6),
            current_mae=round(current_mae, 6),
            relative_change=round(relative_change, 6),
            drift_detected=relative_change > forecast_error_threshold,
        )

    drift_detected = any(result.drift_detected for result in feature_results)
    if forecast_result:
        drift_detected = drift_detected or forecast_result.drift_detected
    return DriftReport(
        feature_results=feature_results,
        forecast_result=forecast_result,
        drift_detected=drift_detected,
    )
