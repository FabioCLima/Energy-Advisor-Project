from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..schemas import UsageForecast
from ..services.usage_forecasting import UsageForecastParams, forecast_energy_usage


@tool
def predict_energy_usage(device_type: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    """Predict expected hourly energy usage from historical patterns (baseline ML).

    This tool provides a deterministic, data-grounded baseline forecast based on
    the household's historical usage. It is useful for:
    - anticipating spikes (EV charging nights, home-office hours)
    - planning flexible loads in cheaper tariff windows
    - supporting explanations with "baseline" vs "optimized" behavior

    Args:
        device_type: Optional device category filter (e.g., "ev", "hvac", "appliance").
        horizon_hours: Forecast horizon in hours (1–168). Default 24.
    """
    if not (1 <= int(horizon_hours) <= 168):
        return {"error": "horizon_hours must be between 1 and 168."}

    try:
        settings = Settings()
        logger.debug(
            "predict_energy_usage | device_type={} horizon_hours={}",
            device_type,
            horizon_hours,
        )
        payload = forecast_energy_usage(
            db_path=settings.db_path,
            device_type=device_type,
            params=UsageForecastParams(horizon_hours=int(horizon_hours)),
        )
        validated = UsageForecast.model_validate(payload)
        return validated.model_dump()
    except Exception as exc:
        logger.exception("predict_energy_usage failed")
        return {"error": f"Failed to forecast energy usage: {exc}"}
