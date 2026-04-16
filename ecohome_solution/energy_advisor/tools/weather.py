from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..schemas import WeatherForecast
from ..services.forecasting import generate_hourly_forecast


@tool
def get_weather_forecast(location: str, days: int = 3) -> dict[str, Any]:
    """Get a synthetic weather forecast for a location.

    Returns hourly temperature, solar irradiance, humidity, and wind speed.
    Data is deterministically generated per location and date — ideal for
    reproducible testing and scheduling logic without external API calls.

    Args:
        location: City or location name.
        days: Number of forecast days (1–7, default 3).
    """
    if not location or not location.strip():
        return {"error": "location must be a non-empty string."}
    if not (1 <= days <= 7):
        return {"error": "days must be between 1 and 7."}

    logger.debug("get_weather_forecast | location={} days={}", location, days)
    payload = generate_hourly_forecast(location=location, days=days)
    validated = WeatherForecast.model_validate(payload)
    return validated.model_dump()
