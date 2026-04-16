from __future__ import annotations

from datetime import datetime


def generate_time_of_use_prices(date: str | None = None) -> dict[str, object]:
    """
    Synthetic time-of-use pricing schedule.
    Peak: 18-22, Mid: 6-18 and 22-23, Off: 0-6.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    base = 0.12
    hourly_rates: list[dict] = []
    for hour in range(24):
        if 0 <= hour < 6:
            period = "off_peak"
            rate = base * 0.75
            demand_charge = 0.0
        elif 18 <= hour < 22:
            period = "peak"
            rate = base * 1.75
            demand_charge = 0.05
        else:
            period = "mid_peak"
            rate = base * 1.10
            demand_charge = 0.0

        hourly_rates.append(
            {
                "hour": hour,
                "rate": round(rate, 4),
                "period": period,
                "demand_charge": round(demand_charge, 4),
            }
        )

    return {
        "date": date,
        "pricing_type": "time_of_use",
        "currency": "USD",
        "unit": "per_kWh",
        "hourly_rates": hourly_rates,
    }

