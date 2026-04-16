from .energy_data import (
    get_recent_energy_summary,
    query_energy_usage,
    query_solar_generation,
)
from .pricing import get_electricity_prices
from .rag import search_energy_tips
from .savings import calculate_energy_savings
from .weather import get_weather_forecast

TOOL_KIT = [
    get_weather_forecast,
    get_electricity_prices,
    query_energy_usage,
    query_solar_generation,
    get_recent_energy_summary,
    search_energy_tips,
    calculate_energy_savings,
]

__all__ = ["TOOL_KIT"]

