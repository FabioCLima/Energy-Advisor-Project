from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from loguru import logger

from .database import DatabaseManager, EnergyUsage


@dataclass(frozen=True)
class UsageForecastParams:
    """Configuration for baseline energy-usage forecasting."""

    horizon_hours: int = 24
    lookback_weeks: int = 8


def _floor_to_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _hour_of_week(dt: datetime) -> int:
    """0..167 where 0=Mon 00:00."""
    return dt.weekday() * 24 + dt.hour


def load_hourly_usage_series(
    db: DatabaseManager,
    device_type: str | None = None,
) -> pd.Series:
    """Return an hourly time series (kWh) from SQLite.

    Missing hours are filled with 0.0 so downstream forecasting can assume
    a continuous series.
    """
    session = db.get_session()
    try:
        q = session.query(
            EnergyUsage.timestamp,  # type: ignore[attr-defined]
            EnergyUsage.consumption_kwh,  # type: ignore[attr-defined]
            EnergyUsage.device_type,  # type: ignore[attr-defined]
        )
        if device_type:
            q = q.filter(EnergyUsage.device_type == device_type)  # type: ignore[attr-defined]
        rows = q.order_by(EnergyUsage.timestamp).all()  # type: ignore[attr-defined]
    finally:
        session.close()

    if not rows:
        return pd.Series(dtype="float64")

    df = pd.DataFrame(rows, columns=["timestamp", "consumption_kwh", "device_type"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    grouped = df.groupby("timestamp", as_index=True)["consumption_kwh"].sum().sort_index()

    start = _floor_to_hour(grouped.index.min().to_pydatetime())
    end = _floor_to_hour(grouped.index.max().to_pydatetime())
    full_index = pd.date_range(start=start, end=end, freq="h")
    return grouped.reindex(full_index, fill_value=0.0)


def seasonal_naive_usage_forecast(
    series: pd.Series,
    params: UsageForecastParams,
    reference_time: datetime | None = None,
) -> list[dict]:
    """Baseline forecast using the mean of prior weeks for the same hour-of-week.

    This is intentionally simple and robust:
    - no external ML dependencies
    - deterministic given the same input series
    - easy to explain in interviews (strong baseline)
    """
    if params.horizon_hours < 1 or params.horizon_hours > 168:
        raise ValueError("horizon_hours must be between 1 and 168.")
    if params.lookback_weeks < 1 or params.lookback_weeks > 52:
        raise ValueError("lookback_weeks must be between 1 and 52.")

    if series.empty:
        return []

    ref = _floor_to_hour(reference_time or datetime.now())
    # Use only observations strictly before forecast start.
    history = series[series.index < ref]
    if history.empty:
        return []

    how = history.index.map(lambda ts: _hour_of_week(ts.to_pydatetime()))
    hist_df = pd.DataFrame({"kwh": history.values, "how": how}, index=history.index)

    horizon: list[dict] = []
    for i in range(params.horizon_hours):
        ts = ref + timedelta(hours=i)
        target_how = _hour_of_week(ts)

        matches = hist_df[hist_df["how"] == target_how]["kwh"]
        if not matches.empty:
            yhat = float(matches.tail(params.lookback_weeks).mean())
        else:
            hod_vals = history[history.index.hour == ts.hour]
            yhat = float(hod_vals.mean()) if not hod_vals.empty else 0.0

        horizon.append(
            {
                "timestamp": ts.isoformat(timespec="minutes"),
                "predicted_kwh": round(yhat, 4),
            }
        )

    return horizon


def forecast_energy_usage(
    db_path: str,
    device_type: str | None = None,
    params: UsageForecastParams | None = None,
    reference_time: datetime | None = None,
) -> dict:
    params = params or UsageForecastParams()
    db = DatabaseManager(db_path=db_path)
    series = load_hourly_usage_series(db, device_type=device_type)
    points = seasonal_naive_usage_forecast(series, params=params, reference_time=reference_time)

    logger.debug(
        "forecast_energy_usage | device_type={} horizon_hours={} points={}",
        device_type,
        params.horizon_hours,
        len(points),
    )

    return {
        "device_type": device_type,
        "method": "seasonal_naive",
        "horizon_hours": params.horizon_hours,
        "points": points,
        "total_predicted_kwh": round(sum(p["predicted_kwh"] for p in points), 4),
    }
