"""Prompt rendering tests — single source of truth for prices and persona."""
from __future__ import annotations

import re

from energy_advisor.profile import UserProfile
from energy_advisor.prompts import SYSTEM_INSTRUCTIONS, render_instructions


def test_prompt_contains_no_hardcoded_tariff_values() -> None:
    # Prices live in the pricing service; a prompt that quotes R$/kWh values
    # duplicates the source of truth and diverges silently.
    assert not re.search(r"R\$\s?0[.,]\d+", SYSTEM_INSTRUCTIONS)


def test_prompt_instructs_fetching_prices_via_tool() -> None:
    assert "get_electricity_prices" in SYSTEM_INSTRUCTIONS
    assert "NEVER quote a tariff value from memory" in SYSTEM_INSTRUCTIONS


def test_prompt_requires_disclosing_synthetic_fallback() -> None:
    assert 'data_source="synthetic"' in SYSTEM_INSTRUCTIONS
    assert "Assumptions & limitations" in SYSTEM_INSTRUCTIONS


def test_default_profile_renders_joao() -> None:
    assert "João" in SYSTEM_INSTRUCTIONS
    assert "Enel SP" in SYSTEM_INSTRUCTIONS
    assert '"PC Home-Office (Ryzen 7)"' in SYSTEM_INSTRUCTIONS


def test_prompt_renders_from_any_profile() -> None:
    maria = UserProfile(
        name="Maria",
        city="Recife, PE",
        distributor="Neoenergia PE",
        solar_description="2kWp rooftop system",
        ev_description="BYD Dolphin — charges weekends",
        home_office_description="Hybrid Tue/Thu",
        home_office_devices=["Notebook Dell"],
        usage_patterns_note='"always_on" (fridge)',
    )

    rendered = render_instructions(maria)

    assert "Maria" in rendered
    assert "Neoenergia PE" in rendered
    assert "João" not in rendered
