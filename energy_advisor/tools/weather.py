from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..schemas import WeatherForecast
from ..services.forecasting import generate_hourly_forecast


@tool
def get_weather_forecast(location: str, days: int = 3) -> dict[str, Any]:
    """Get a real-time weather forecast for a location using the Open-Meteo API.

    Returns today's hourly temperature, solar irradiance (W/m²), humidity, and
    wind speed. Falls back to deterministic synthetic data when the API is
    unreachable. Check 'data_source' in the response: 'open_meteo' = real data,
    'synthetic' = fallback.

    Solar irradiance (direct_radiation + diffuse_radiation) is the key input for
    estimating photovoltaic panel generation. Peak values above 600 W/m² indicate
    strong solar generation hours.

    Args:
        location: City or location name (currently resolved to São Paulo, SP).
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
