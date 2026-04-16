from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..services.recommendations import compute_savings


@tool
def calculate_energy_savings(
    device_type: str,
    current_usage_kwh: float,
    optimized_usage_kwh: float,
    price_per_kwh: float = 0.12,
) -> dict[str, Any]:
    """Calculate potential energy and cost savings from optimising device usage.

    Args:
        device_type: Human-readable device name, e.g. 'EV charger', 'HVAC'.
        current_usage_kwh: Baseline daily consumption in kWh.
        optimized_usage_kwh: Expected consumption after optimisation in kWh.
        price_per_kwh: Electricity price in USD/kWh (default 0.12).
    """
    if current_usage_kwh < 0 or optimized_usage_kwh < 0:
        return {"error": "usage values must be non-negative."}
    if price_per_kwh <= 0:
        return {"error": "price_per_kwh must be positive."}

    logger.debug(
        "calculate_energy_savings | device={} current={}kWh optimized={}kWh price=${}",
        device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh,
    )
    result = compute_savings(device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh)
    return result.model_dump()
