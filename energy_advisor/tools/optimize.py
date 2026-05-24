"""LangGraph tool: energy schedule optimizer."""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..services.optimizer import generate_recommendations


@tool
def optimize_energy_schedule(horizon_days: int = 30) -> dict[str, Any]:
    """Generate ranked energy optimization recommendations for João.

    Crosses a 7-day ML usage forecast with the TOU tariff schedule to
    identify which loads to shift, when, and how much money that saves.

    Args:
        horizon_days: Projection horizon for savings (1–90 days, default 30).

    Returns:
        Dict with 'recommendations' list, each containing:
          - rank, device_type, label, action
          - current_window, optimal_window
          - savings_30d_brl, savings_90d_brl
          - confidence ('high'|'medium'|'low'), method ('sklearn_hgb'|'seasonal_naive')
    """
    if not (1 <= int(horizon_days) <= 90):
        return {"error": "horizon_days must be between 1 and 90."}

    try:
        settings = Settings()
        recs = generate_recommendations(
            db_path=settings.db_path,
            horizon_days=int(horizon_days),
        )

        logger.debug(
            "optimize_energy_schedule | horizon_days={} recommendations={}",
            horizon_days, len(recs),
        )

        return {
            "horizon_days": horizon_days,
            "recommendations": [
                {
                    "rank":              r.rank,
                    "device_type":       r.device_type,
                    "label":             r.label,
                    "action":            r.action,
                    "current_window":    r.current_window,
                    "optimal_window":    r.optimal_window,
                    "savings_7d_brl":    r.savings_7d_brl,
                    "savings_30d_brl":   r.savings_30d_brl,
                    "savings_90d_brl":   r.savings_90d_brl,
                    "confidence":        r.confidence,
                    "method":            r.method,
                    "peak_kwh":          r.peak_kwh_predicted,
                    "mid_kwh":           r.mid_kwh_predicted,
                }
                for r in recs
            ],
            "total_savings_30d_brl": round(sum(r.savings_30d_brl for r in recs), 2),
            "total_savings_90d_brl": round(sum(r.savings_90d_brl for r in recs), 2),
        }

    except Exception as exc:
        logger.exception("optimize_energy_schedule failed")
        return {"error": f"Failed to generate recommendations: {exc}"}
