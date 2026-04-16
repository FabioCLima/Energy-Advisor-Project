from __future__ import annotations

from typing import Any

from ..schemas import SavingsResult


def compute_savings(
    device_type: str,
    current_usage_kwh: float,
    optimized_usage_kwh: float,
    price_per_kwh: float = 0.12,
) -> SavingsResult:
    """
    Core savings calculation.

    Returns a validated SavingsResult. All arithmetic lives here —
    the savings tool is a thin wrapper that calls this function.
    """
    savings_kwh = current_usage_kwh - optimized_usage_kwh
    savings_usd = savings_kwh * price_per_kwh
    savings_pct = (savings_kwh / current_usage_kwh * 100) if current_usage_kwh > 0 else 0.0

    return SavingsResult(
        device_type=device_type,
        current_usage_kwh=current_usage_kwh,
        optimized_usage_kwh=optimized_usage_kwh,
        savings_kwh=round(savings_kwh, 2),
        savings_usd=round(savings_usd, 2),
        savings_percentage=round(savings_pct, 1),
        price_per_kwh=price_per_kwh,
        annual_savings_usd=round(savings_usd * 365, 2),
    )


def best_charging_windows(
    hourly_rates: list[dict[str, Any]],
    solar_hourly: list[dict[str, Any]] | None = None,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """
    Identify the cheapest hours to run flexible loads (e.g. EV charging).

    If solar data is provided, hours with high generation are boosted so the
    agent can also recommend solar self-consumption windows.

    Returns a list of dicts sorted by effective cost (ascending).
    """
    scored = []
    for rate in hourly_rates:
        hour = rate["hour"]
        base_cost = rate["rate"]

        solar_bonus = 0.0
        if solar_hourly:
            match = next((s for s in solar_hourly if s.get("hour") == hour), None)
            if match:
                irradiance = match.get("solar_irradiance", 0.0)
                solar_bonus = min(irradiance / 1000.0 * 0.03, 0.02)

        effective_cost = base_cost - solar_bonus
        scored.append(
            {
                "hour": hour,
                "period": rate.get("period", "unknown"),
                "rate_per_kwh": base_cost,
                "solar_bonus": round(solar_bonus, 4),
                "effective_cost": round(effective_cost, 4),
            }
        )

    scored.sort(key=lambda x: x["effective_cost"])
    return scored[:top_n]


def build_recommendation_context(
    usage: dict[str, Any] | None = None,
    solar: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
    tips: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Assemble a structured context dict from multiple tool results.

    This is a convenience helper for agents or notebooks that want to
    bundle all available evidence before asking the LLM to summarise.
    """
    return {
        "energy_usage": usage,
        "solar_generation": solar,
        "weather_forecast": weather,
        "electricity_pricing": pricing,
        "knowledge_tips": tips or [],
    }
