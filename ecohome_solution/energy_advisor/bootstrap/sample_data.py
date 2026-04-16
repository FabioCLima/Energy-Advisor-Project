"""
Bootstrap step 2: Sample data generation.

Generates 30 days of realistic synthetic energy usage and solar generation
records so the agent has data to reason about on a fresh install.

Usage:
    python -m energy_advisor.bootstrap.sample_data
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager

# ── Device profiles ───────────────────────────────────────────────────
# Each entry: (device_type, device_name, hourly_kwh_range, active_hours)
_DEVICE_PROFILES = [
    ("EV",        "Tesla Model 3",    (1.5, 7.2),  list(range(22, 24)) + list(range(0, 6))),
    ("HVAC",      "Main AC",          (0.8, 2.5),  list(range(9, 22))),
    ("appliance", "Washing Machine",  (0.5, 1.2),  [9, 10, 14, 15]),
    ("appliance", "Dishwasher",       (0.3, 0.9),  [20, 21]),
    ("appliance", "Water Heater",     (1.0, 2.0),  [6, 7, 18, 19]),
    ("lighting",  "LED Lighting",     (0.05, 0.2), list(range(18, 24)) + list(range(0, 7))),
]


def load_sample_data(
    settings: Settings | None = None,
    days: int = 30,
    seed: int = 42,
) -> None:
    """Populate the database with synthetic energy and solar data.

    Idempotent: skips loading if rows already exist.

    Args:
        settings: Optional Settings instance.
        days: Number of historical days to generate (default 30).
        seed: Random seed for reproducibility.
    """
    settings = settings or Settings()
    db = DatabaseManager(db_path=settings.db_path)
    db.create_tables()

    if db.count_usage_records() > 0:
        logger.info(
            "Sample data already present ({} usage records) — skipping.",
            db.count_usage_records(),
        )
        return

    rng = random.Random(seed)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    logger.info("Generating {} days of sample energy data (seed={})...", days, seed)
    usage_count = 0
    solar_count = 0

    current = start
    while current <= now:
        hour = current.hour

        # ── Energy usage ──────────────────────────────────────────────
        for device_type, device_name, (lo, hi), active_hours in _DEVICE_PROFILES:
            if hour in active_hours:
                kwh = round(rng.uniform(lo, hi), 3)
                # Simple TOU pricing
                if 18 <= hour < 22:
                    rate = 0.21
                elif 0 <= hour < 6:
                    rate = 0.09
                else:
                    rate = 0.13
                cost = round(kwh * rate, 4)
                db.add_usage_record(
                    timestamp=current,
                    consumption_kwh=kwh,
                    device_type=device_type,
                    device_name=device_name,
                    cost_usd=cost,
                )
                usage_count += 1

        # ── Solar generation ─────────────────────────────────────────
        daylight_factor = max(0.0, 1.0 - abs(hour - 12) / 7)
        if daylight_factor > 0:
            conditions = ["sunny", "partly_cloudy", "cloudy"]
            condition = rng.choice(conditions)
            cloud = {"sunny": 1.0, "partly_cloudy": 0.65, "cloudy": 0.3}[condition]
            base_temp = rng.uniform(18.0, 30.0)
            irradiance = round(900.0 * daylight_factor * cloud + rng.uniform(-20, 20), 1)
            irradiance = max(0.0, irradiance)
            generation = round(irradiance / 1000.0 * 5.0 * rng.uniform(0.85, 1.0), 3)  # 5 kW panel
            db.add_generation_record(
                timestamp=current,
                generation_kwh=generation,
                weather_condition=condition,
                temperature_c=round(base_temp + rng.uniform(-2, 2), 1),
                solar_irradiance=irradiance,
            )
            solar_count += 1

        current += timedelta(hours=1)

    logger.info(
        "Sample data loaded: {} usage records, {} solar records.",
        usage_count,
        solar_count,
    )


if __name__ == "__main__":
    load_sample_data()
