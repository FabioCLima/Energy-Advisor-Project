from __future__ import annotations

import hashlib
import random
from datetime import datetime

import requests

# ── Open-Meteo constants ──────────────────────────────────────────────
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# João's location — São Paulo, SP
_SAO_PAULO_LAT = -23.5505
_SAO_PAULO_LON = -46.6333

# WMO weather code → human-readable condition
# https://open-meteo.com/en/docs#weathervariables
_WMO_CONDITION: dict[int, str] = {
    0: "sunny",
    1: "sunny", 2: "partly_cloudy", 3: "cloudy",
    45: "foggy", 48: "foggy",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    56: "drizzle", 57: "drizzle",
    61: "rain", 63: "rain", 65: "rain",
    66: "rain", 67: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "rain",
    85: "snow", 86: "snow",
    95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm",
}


def _sanitize_temperature_c(value: float | int | None) -> float | None:
    """Return plausible Sao Paulo ambient temperature for dashboard display.

    Open-Meteo can occasionally return missing or obviously wrong values in
    degraded network/test conditions. For this demo, hide implausible readings
    instead of surfacing impossible temperatures like -15°C for Sao Paulo.
    """
    if value is None:
        return None
    temp = float(value)
    if temp < 5.0 or temp > 45.0:
        return None
    return round(temp, 1)


def _fetch_open_meteo(lat: float, lon: float, days: int) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "temperature_2m,relative_humidity_2m,wind_speed_10m,"
            "direct_radiation,diffuse_radiation,weathercode"
        ),
        "timezone": "America/Sao_Paulo",
        "forecast_days": days,
    }
    response = requests.get(_OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _parse_open_meteo(raw: dict, days: int) -> dict:
    """Convert Open-Meteo response into the WeatherForecast dict format.

    Returns today's 24-hour hourly slice. solar_irradiance = direct + diffuse (W/m²).
    """
    h = raw["hourly"]
    times = h["time"]  # e.g. "2026-05-23T14:00"

    hourly: list[dict] = []
    for i in range(min(24, len(times))):
        hour = int(times[i].split("T")[1].split(":")[0])
        irradiance = (h["direct_radiation"][i] or 0.0) + (h["diffuse_radiation"][i] or 0.0)
        wmo = int(h["weathercode"][i] or 0)
        hourly.append({
            "hour":             hour,
            "temperature_c":    _sanitize_temperature_c(h["temperature_2m"][i]),
            "condition":        _WMO_CONDITION.get(wmo, "partly_cloudy"),
            "solar_irradiance": round(irradiance, 1),
            "humidity":         int(h["relative_humidity_2m"][i] or 50),
            "wind_speed":       round(h["wind_speed_10m"][i] or 0.0, 1),
        })

    now_h = datetime.now().hour
    current = next((d for d in hourly if d["hour"] == now_h), hourly[0])

    return {
        "location":      f"São Paulo, SP ({raw['latitude']:.4f}, {raw['longitude']:.4f})",
        "forecast_days": days,
        "data_source":   "open_meteo",
        "current": {
            "temperature_c": current.get("temperature_c"),
            "condition":     current["condition"],
            "humidity":      current["humidity"],
            "wind_speed":    current["wind_speed"],
        },
        "hourly": hourly,
    }


def generate_hourly_forecast(location: str, days: int) -> dict:
    """Return hourly weather forecast for São Paulo.

    Tries Open-Meteo API (real data) first; falls back to deterministic
    synthetic data when the API is unreachable.
    """
    days = max(1, min(int(days), 7))
    try:
        raw = _fetch_open_meteo(_SAO_PAULO_LAT, _SAO_PAULO_LON, days)
        return _parse_open_meteo(raw, days)
    except Exception:
        return _synthetic_fallback(location, days)


# ── Synthetic fallback ────────────────────────────────────────────────

def _seed_from(location: str, date: str) -> int:
    payload = f"{location}|{date}".encode()
    return int(hashlib.sha256(payload).hexdigest()[:8], 16)


def _synthetic_fallback(location: str, days: int) -> dict:
    """Deterministic synthetic forecast — used only when Open-Meteo is unreachable."""
    today = datetime.now().strftime("%Y-%m-%d")
    rng = random.Random(_seed_from(location, today))

    base_temp     = rng.uniform(18.0, 30.0)
    base_humidity = rng.randint(35, 80)
    base_wind     = rng.uniform(1.0, 8.0)
    condition     = rng.choice(["sunny", "partly_cloudy", "cloudy"])

    hourly: list[dict] = []
    for hour in range(24):
        delta = (
            -4.0 if hour < 6
            else 0.5 * (hour - 6) if hour < 15
            else 0.5 * (15 - hour)
        )
        temp = base_temp + delta + rng.uniform(-1.0, 1.0)

        daylight_factor = max(0.0, 1.0 - abs(hour - 12) / 12)
        cloud_factor    = {"sunny": 1.0, "partly_cloudy": 0.7, "cloudy": 0.4}[condition]
        irradiance      = max(0.0, 900.0 * daylight_factor * cloud_factor + rng.uniform(-30.0, 30.0))

        hourly.append({
            "hour":             hour,
            "temperature_c":    _sanitize_temperature_c(temp),
            "condition":        condition,
            "solar_irradiance": round(irradiance, 1),
            "humidity":         int(max(10, min(100, base_humidity + rng.randint(-5, 5)))),
            "wind_speed":       round(max(0.0, base_wind + rng.uniform(-1.0, 1.0)), 1),
        })

    now_h = datetime.now().hour
    return {
        "location":      location,
        "forecast_days": days,
        "data_source":   "synthetic",
        "current": {
            "temperature_c": hourly[now_h].get("temperature_c"),
            "condition":     condition,
            "humidity":      hourly[now_h]["humidity"],
            "wind_speed":    hourly[now_h]["wind_speed"],
        },
        "hourly": hourly,
    }
