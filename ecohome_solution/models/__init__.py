# Backwards-compatibility shim.
# All models now live in energy_advisor.services.database — import from there.
from energy_advisor.services.database import DatabaseManager, EnergyUsage, SolarGeneration

__all__ = ["DatabaseManager", "EnergyUsage", "SolarGeneration"]
