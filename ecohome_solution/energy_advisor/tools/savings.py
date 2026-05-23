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
    price_per_kwh: float = 0.656,
) -> dict[str, Any]:
    """Calcula economia potencial de energia e custo ao otimizar o uso de um dispositivo.

    Args:
        device_type: Nome do dispositivo, ex: 'Chuveiro Elétrico', 'AC Escritório'.
        current_usage_kwh: Consumo diário atual em kWh.
        optimized_usage_kwh: Consumo esperado após otimização em kWh.
        price_per_kwh: Tarifa em R$/kWh (padrão: Enel SP fora de ponta 0.656).
    """
    if current_usage_kwh < 0 or optimized_usage_kwh < 0:
        return {"error": "usage values must be non-negative."}
    if price_per_kwh <= 0:
        return {"error": "price_per_kwh must be positive."}

    logger.debug(
        "calculate_energy_savings | device={} current={}kWh optimized={}kWh price=R${}",
        device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh,
    )
    result = compute_savings(device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh)
    return result.model_dump()
