"""Tests for energy_advisor.services.pricing."""
from __future__ import annotations

from datetime import datetime

from energy_advisor.services.pricing import generate_time_of_use_prices


def test_returns_24_hourly_rates():
    result = generate_time_of_use_prices()
    assert result["pricing_type"] == "time_of_use"
    assert len(result["hourly_rates"]) == 24


def test_off_peak_hours():
    result = generate_time_of_use_prices()
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    for h in range(0, 6):
        assert rates[h]["period"] == "off_peak", f"Hour {h} should be off_peak"
        assert rates[h]["rate"] < 0.10


def test_peak_hours():
    result = generate_time_of_use_prices()
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    for h in range(18, 22):
        assert rates[h]["period"] == "peak", f"Hour {h} should be peak"
        assert rates[h]["rate"] > 0.18
        assert rates[h]["demand_charge"] > 0.0


def test_mid_peak_hours():
    result = generate_time_of_use_prices()
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    for h in list(range(6, 18)) + [22, 23]:
        assert rates[h]["period"] == "mid_peak", f"Hour {h} should be mid_peak"


def test_date_defaults_to_today():
    result = generate_time_of_use_prices()
    assert result["date"] == datetime.now().strftime("%Y-%m-%d")


def test_explicit_date():
    result = generate_time_of_use_prices(date="2025-06-01")
    assert result["date"] == "2025-06-01"


def test_all_rates_positive():
    result = generate_time_of_use_prices()
    for r in result["hourly_rates"]:
        assert r["rate"] > 0, f"Rate at hour {r['hour']} should be positive"
