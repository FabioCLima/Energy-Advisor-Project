from __future__ import annotations

import pandas as pd
import pytest

from energy_advisor.services.drift_monitor import monitor_energy_drift


def test_monitor_energy_drift_passes_when_windows_are_stable() -> None:
    baseline = pd.DataFrame({"kwh": [10.0, 11.0, 9.0], "actual": [10.0, 11.0, 9.0], "pred": [9.5, 11.5, 9.2]})
    current = pd.DataFrame({"kwh": [10.5, 10.8, 9.7], "actual": [10.5, 10.8, 9.7], "pred": [10.1, 11.2, 9.9]})

    report = monitor_energy_drift(
        baseline,
        current,
        feature_columns=["kwh"],
        actual_col="actual",
        prediction_col="pred",
    )

    assert report.drift_detected is False
    assert report.feature_results[0].drift_detected is False
    assert report.forecast_result is not None
    assert report.forecast_result.drift_detected is False


def test_monitor_energy_drift_flags_mean_shift() -> None:
    baseline = pd.DataFrame({"kwh": [10.0, 10.0, 10.0]})
    current = pd.DataFrame({"kwh": [15.0, 15.0, 15.0]})

    report = monitor_energy_drift(baseline, current, feature_columns=["kwh"])

    assert report.drift_detected is True
    assert report.feature_results[0].relative_change == 0.5


def test_monitor_energy_drift_flags_forecast_error_degradation() -> None:
    baseline = pd.DataFrame({"kwh": [10.0, 10.0], "pred": [9.0, 11.0]})
    current = pd.DataFrame({"kwh": [10.0, 10.0], "pred": [5.0, 15.0]})

    report = monitor_energy_drift(
        baseline,
        current,
        feature_columns=["kwh"],
        actual_col="kwh",
        prediction_col="pred",
    )

    assert report.drift_detected is True
    assert report.forecast_result is not None
    assert report.forecast_result.baseline_mae == 1.0
    assert report.forecast_result.current_mae == 5.0


def test_monitor_energy_drift_rejects_missing_feature() -> None:
    with pytest.raises(ValueError, match="Feature column"):
        monitor_energy_drift(
            pd.DataFrame({"kwh": [1.0]}),
            pd.DataFrame({"other": [1.0]}),
            feature_columns=["kwh"],
        )
