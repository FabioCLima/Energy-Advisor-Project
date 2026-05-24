from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..schemas import UsageForecast
from ..services.forecast_router import route_usage_forecast
from ..services.usage_forecasting import UsageForecastParams


@tool
def predict_energy_usage(device_type: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    """Predict expected hourly energy usage from historical patterns."""
    if not (1 <= int(horizon_hours) <= 168):
        return {"error": "horizon_hours must be between 1 and 168."}

    try:
        settings = Settings()
        params = UsageForecastParams(horizon_hours=int(horizon_hours))
        payload = route_usage_forecast(
            db_path=settings.db_path,
            device_type=device_type,
            params=params,
        )
        logger.debug(
            "predict_energy_usage | device_type={} horizon_hours={} method={}",
            device_type,
            horizon_hours,
            payload.get("method"),
        )
        validated = UsageForecast.model_validate(payload)
        return validated.model_dump()
    except Exception as exc:
        logger.exception("predict_energy_usage failed")
        return {"error": f"Failed to forecast energy usage: {exc}"}
