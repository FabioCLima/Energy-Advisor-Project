"""
Energy optimizer service — Layer 2 of the ML feature.

Takes a 7-day ML/baseline usage forecast, crosses it with the TOU
tariff schedule, and surfaces ranked savings opportunities with
quantified R$ impact.

Design constraints (scope):
  - Horizon: up to 90 days of historical data, recommendations up to 30 days.
  - No RL, no online learning — pure forecast × tariff arbitrage.
  - Shiftability factors per device type encode domain knowledge
    about which loads can actually be moved to off-peak windows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from .pricing import generate_time_of_use_prices
from .forecast_router import route_usage_forecast
from .usage_forecasting import UsageForecastParams


# ── Forecast routing ───────────────────────────────────────────────

# ── Tariff constants (Enel SP, Bandeira Verde) ────────────────────────
_OFF_PEAK_RATE = 0.538   # 0h–5h
_MID_PEAK_RATE = 0.656   # 6h–17h, 21h–23h
_PEAK_RATE     = 0.987   # 18h–20h

# Hours where consumption should ideally be avoided or shifted
_PEAK_HOURS    = frozenset(range(18, 21))
_OFF_PEAK_HOURS = frozenset(range(0, 6))

# ── Device profile ────────────────────────────────────────────────────
# shiftable_from_peak:   fraction of peak-hour load that CAN be moved
# shiftable_from_mid:    fraction of mid-peak load that CAN be moved
# action / windows: human-readable recommendation text
_DEVICE_PROFILES: dict[str, dict] = {
    "ev": {
        "label":               "EV Charging (Tesla Model 3)",
        "shiftable_from_peak": 0.90,
        "shiftable_from_mid":  0.85,
        "action": (
            "Schedule charging between 0h–5h (off-peak) instead of "
            "evening hours. Tesla app supports scheduled charging."
        ),
        "current_window": "mixed hours (some peak/mid-peak)",
        "optimal_window": "0h–5h (off-peak · R$ 0.538/kWh)",
    },
    "appliance": {
        "label":               "Appliances (washer, dishwasher)",
        "shiftable_from_peak": 0.80,
        "shiftable_from_mid":  0.50,
        "action": (
            "Shift washing machine and dishwasher cycles to 0h–5h. "
            "Most modern appliances have delay-start timers."
        ),
        "current_window": "morning / evening (mid-peak)",
        "optimal_window": "0h–5h (off-peak · R$ 0.538/kWh)",
    },
    "hvac": {
        "label":               "AC Escritório (12k BTU Inverter)",
        "shiftable_from_peak": 0.40,
        "shiftable_from_mid":  0.10,
        "action": (
            "Pre-cool the office to 22°C by 17h30 before peak window "
            "(18h–20h). Inverter AC maintains temperature with lower "
            "power draw. Avoid heavy usage between 18h–20h."
        ),
        "current_window": "10h–17h (mid-peak) + risk of 18h spillover",
        "optimal_window": "pre-cool 17h–17h59 · off during 18h–20h",
    },
}

# ── Data model ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Recommendation:
    rank: int
    device_type: str
    label: str
    action: str
    current_window: str
    optimal_window: str
    savings_7d_brl: float        # over the 7-day forecast window
    savings_30d_brl: float       # projected to 30 days
    savings_90d_brl: float       # projected to 90 days (3-month cap)
    confidence: str              # "high" | "medium" | "low"
    method: str                  # "sklearn_hgb" | "seasonal_naive"
    peak_kwh_predicted: float    # kWh forecast in peak hours (7d)
    mid_kwh_predicted: float     # kWh forecast in mid-peak hours (7d)


# ── Core calculation ──────────────────────────────────────────────────

def _savings_for_forecast(
    points: list[dict],
    profile: dict,
    hourly_rates: dict[int, float],
) -> tuple[float, float, float]:
    """Return (savings_brl, peak_kwh, mid_kwh) for a 7-day forecast.

    Logic: for each predicted hour, if the load falls in a non-optimal
    window AND is shiftable, compute the cost delta vs off-peak rate.
    """
    savings = 0.0
    peak_kwh = 0.0
    mid_kwh  = 0.0

    shift_peak = profile["shiftable_from_peak"]
    shift_mid  = profile["shiftable_from_mid"]

    for point in points:
        hour = int(point["timestamp"][11:13])
        kwh  = point["predicted_kwh"]
        rate = hourly_rates.get(hour, _MID_PEAK_RATE)

        if hour in _PEAK_HOURS:
            peak_kwh += kwh
            savings  += kwh * shift_peak * (rate - _OFF_PEAK_RATE)
        elif hour not in _OFF_PEAK_HOURS:
            mid_kwh += kwh
            savings += kwh * shift_mid * (rate - _OFF_PEAK_RATE)

    return max(0.0, savings), peak_kwh, mid_kwh


def _confidence(method: str, savings_7d: float) -> str:
    if method == "sklearn_hgb" and savings_7d > 1.0:
        return "high"
    if method == "sklearn_hgb":
        return "medium"
    return "low"


# ── Public API ────────────────────────────────────────────────────────

def generate_recommendations(
    db_path: str,
    horizon_days: int = 30,
) -> list[Recommendation]:
    """Generate ranked energy savings recommendations.

    Uses 7-day ML/baseline forecast per device type, crosses with TOU
    tariff, and projects savings over horizon_days (max 90).

    Args:
        db_path: Path to the SQLite database.
        horizon_days: Projection horizon in days (1–90).

    Returns:
        List of Recommendation, sorted by 30-day savings descending.
    """
    horizon_days = max(1, min(int(horizon_days), 90))

    # 7-day forecast window (168h) — long enough to capture weekly patterns
    params = UsageForecastParams(horizon_hours=168)

    # TOU hourly rates for today (bandeira included)
    pricing     = generate_time_of_use_prices()
    hourly_rates = {r["hour"]: r["rate"] for r in pricing["hourly_rates"]}

    recs: list[Recommendation] = []
    for device_type, profile in _DEVICE_PROFILES.items():
        result = route_usage_forecast(
            db_path=db_path,
            device_type=device_type,
            params=params,
        )
        method = result.get("method", "seasonal_naive")
        points = result.get("points", [])

        if not points:
            logger.debug("optimizer: no forecast points for device_type={}", device_type)
            continue

        savings_7d, peak_kwh, mid_kwh = _savings_for_forecast(
            points, profile, hourly_rates
        )

        # Project from 7-day window to requested horizon
        savings_30d = savings_7d * (30.0 / 7.0)
        savings_90d = savings_7d * (90.0 / 7.0)

        logger.debug(
            "optimizer | device={} method={} savings_7d={:.2f} savings_30d={:.2f}",
            device_type, method, savings_7d, savings_30d,
        )

        recs.append(Recommendation(
            rank=0,  # assigned after sorting
            device_type=device_type,
            label=profile["label"],
            action=profile["action"],
            current_window=profile["current_window"],
            optimal_window=profile["optimal_window"],
            savings_7d_brl=round(savings_7d, 2),
            savings_30d_brl=round(savings_30d, 2),
            savings_90d_brl=round(savings_90d, 2),
            confidence=_confidence(method, savings_7d),
            method=method,
            peak_kwh_predicted=round(peak_kwh, 3),
            mid_kwh_predicted=round(mid_kwh, 3),
        ))

    # Sort by 30-day savings, assign rank
    recs.sort(key=lambda r: r.savings_30d_brl, reverse=True)
    return [
        Recommendation(**{**r.__dict__, "rank": i + 1})
        for i, r in enumerate(recs)
    ]
