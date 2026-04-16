from __future__ import annotations

import hashlib
import random
from datetime import datetime


def _seed_from(location: str, date: str) -> int:
    payload = f"{location}|{date}".encode()
    return int(hashlib.sha256(payload).hexdigest()[:8], 16)


def generate_hourly_forecast(location: str, days: int) -> dict[str, object]:
    """
    Synthetic weather forecast generator (deterministic per location+date).
    Keeps the project self-contained while enabling realistic optimization logic.
    """
    days = max(1, min(int(days), 7))
    today = datetime.now().strftime("%Y-%m-%d")
    rng = random.Random(_seed_from(location, today))

    base_temp = rng.uniform(18.0, 30.0)
    base_humidity = rng.randint(35, 80)
    base_wind = rng.uniform(1.0, 8.0)
    condition = rng.choice(["sunny", "partly_cloudy", "cloudy"])

    hourly: list[dict] = []
    for hour in range(24):
        # Simple diurnal temperature curve
        delta = -4.0 if hour < 6 else (0.5 * (hour - 6) if hour < 15 else 0.5 * (15 - hour))
        temp = base_temp + delta + rng.uniform(-1.0, 1.0)

        # Solar irradiance peaks around midday, reduced by cloudiness
        daylight_factor = max(0.0, 1.0 - abs(hour - 12) / 12)
        cloud_factor = {"sunny": 1.0, "partly_cloudy": 0.7, "cloudy": 0.4}[condition]
        irradiance = 900.0 * daylight_factor * cloud_factor + rng.uniform(-30.0, 30.0)
        irradiance = max(0.0, irradiance)

        hourly.append(
            {
                "hour": hour,
                "temperature_c": round(temp, 1),
                "condition": condition,
                "solar_irradiance": round(irradiance, 1),
                "humidity": int(max(10, min(100, base_humidity + rng.randint(-5, 5)))),
                "wind_speed": round(max(0.0, base_wind + rng.uniform(-1.0, 1.0)), 1),
            }
        )

    return {
        "location": location,
        "forecast_days": days,
        "current": {
            "temperature_c": hourly[datetime.now().hour]["temperature_c"],
            "condition": condition,
            "humidity": hourly[datetime.now().hour]["humidity"],
            "wind_speed": hourly[datetime.now().hour]["wind_speed"],
        },
        "hourly": hourly,
    }

