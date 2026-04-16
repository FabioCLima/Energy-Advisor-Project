from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..schemas import ElectricityPrices
from ..services.pricing import generate_time_of_use_prices


@tool
def get_electricity_prices(date: str | None = None) -> dict[str, Any]:
    """Return time-of-use electricity prices for a given date.

    Prices follow a three-tier schedule:
    - Off-peak  (00:00–06:00): lowest rate (~$0.09/kWh)
    - Mid-peak  (06:00–18:00, 22:00–24:00): standard rate (~$0.13/kWh)
    - Peak      (18:00–22:00): highest rate (~$0.21/kWh) + demand charge

    Args:
        date: Target date in YYYY-MM-DD format. Defaults to today.
    """
    logger.debug("get_electricity_prices | date={}", date)
    payload = generate_time_of_use_prices(date=date)
    validated = ElectricityPrices.model_validate(payload)
    return validated.model_dump()
