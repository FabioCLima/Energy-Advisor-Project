from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..schemas import UsageForecast
from ..services.usage_forecasting import UsageForecastParams, forecast_energy_usage


@tool
def predict_energy_usage(device_type: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    """Predict expected hourly energy usage from historical patterns.

    Modes (controlled by ENERGY_ADVISOR_USAGE_FORECAST_MODE):
    - baseline: seasonal naive (no ML deps)
    - ml: sklearn model from data/models/ (requires training step)
    - auto: use ml if model exists, otherwise baseline

    Args:
        device_type: Optional device category filter (e.g., "ev", "hvac", "appliance").
        horizon_hours: Forecast horizon in hours (1–168). Default 24.
    """
    if not (1 <= int(horizon_hours) <= 168):
        return {"error": "horizon_hours must be between 1 and 168."}

    try:
        settings = Settings()
        params = UsageForecastParams(horizon_hours=int(horizon_hours))
        mode = settings.usage_forecast_mode
        model_path = settings.usage_forecast_model_path(device_type)

        logger.debug(
            "predict_energy_usage | device_type={} horizon_hours={} mode={} model_path={}",
            device_type,
            horizon_hours,
            mode,
            model_path,
        )

        if mode in {"ml", "auto"} and os.path.exists(model_path):
            from ..services.usage_forecasting_ml import forecast_energy_usage_ml

            payload = forecast_energy_usage_ml(
                db_path=settings.db_path,
                model_path=model_path,
                device_type=device_type,
                params=params,
            )
            validated = UsageForecast.model_validate(payload)
            return validated.model_dump()

        if mode == "ml" and not os.path.exists(model_path):
            return {
                "error": (
                    f"ML model not found at {model_path}. "
                    "Train it with: python -m energy_advisor.bootstrap.ml_train"
                )
            }

        payload = forecast_energy_usage(
            db_path=settings.db_path,
            device_type=device_type,
            params=params,
        )
        validated = UsageForecast.model_validate(payload)
        return validated.model_dump()

    except Exception as exc:
        logger.exception("predict_energy_usage failed")
        return {"error": f"Failed to forecast energy usage: {exc}"}
