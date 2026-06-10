"""UserProfile — the household context the agent serves.

Extracting the persona from the prompt text makes the single-user demo an
explicit, swappable object instead of hardcoded prose: multi-user support
becomes "render the prompt from another profile", not "rewrite the prompt".

Deliberately *not* in the profile: tariff values. Prices come from
get_electricity_prices at runtime — a prompt that both says "do not fabricate
prices" and contains prices is a contradiction waiting to diverge.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Household profile injected into the system prompt."""

    name: str
    city: str
    distributor: str
    solar_description: str = Field(description="PV system size and generation window.")
    ev_description: str = Field(description="EV model and charging habits.")
    home_office_description: str = Field(description="Work pattern relevant to load shifting.")
    home_office_devices: list[str] = Field(
        description="Exact device_name values in the DB that compose the home office."
    )
    usage_patterns_note: str = Field(
        description="Mapping of usage_pattern values in the DB to device examples."
    )

    def home_office_devices_inline(self) -> str:
        return ", ".join(f'"{d}"' for d in self.home_office_devices)


DEFAULT_PROFILE = UserProfile(
    name="João",
    city="São Paulo, SP",
    distributor="Enel SP",
    solar_description="4kWp rooftop system (peak generation 9h–16h)",
    ev_description="Tesla Model 3 Long Range — charges ~3×/week overnight (0h–5h)",
    home_office_description="Home office Mon–Fri",
    home_office_devices=[
        "PC Home-Office (Ryzen 7)",
        'Monitor 27" Dell UltraSharp',
        "AC Escritório Inverter 12k BTU",
    ],
    usage_patterns_note=(
        '"always_on" (fridge, router), "presence_dependent" (home-office, TV), '
        '"scheduled" (EV, washing machine, shower)'
    ),
)
