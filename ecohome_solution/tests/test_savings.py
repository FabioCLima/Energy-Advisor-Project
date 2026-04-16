"""Tests for energy_advisor.services.recommendations.compute_savings."""
from __future__ import annotations

import pytest
from energy_advisor.services.recommendations import compute_savings


def test_basic_savings():
    result = compute_savings(
        device_type="EV charger",
        current_usage_kwh=10.0,
        optimized_usage_kwh=7.0,
        price_per_kwh=0.12,
    )
    assert result.savings_kwh == 3.0
    assert result.savings_usd == pytest.approx(0.36, abs=0.01)
    assert result.savings_percentage == pytest.approx(30.0, abs=0.1)
    assert result.annual_savings_usd == pytest.approx(0.36 * 365, abs=0.5)


def test_zero_savings():
    result = compute_savings("HVAC", 5.0, 5.0, 0.12)
    assert result.savings_kwh == 0.0
    assert result.savings_usd == 0.0
    assert result.savings_percentage == 0.0


def test_zero_current_usage():
    result = compute_savings("Lighting", 0.0, 0.0, 0.12)
    assert result.savings_percentage == 0.0  # no division by zero


def test_full_savings():
    result = compute_savings("Pool pump", 4.0, 0.0, 0.15)
    assert result.savings_kwh == 4.0
    assert result.savings_percentage == 100.0


def test_annual_is_daily_times_365():
    result = compute_savings("Washer", 2.0, 1.5, 0.10)
    assert result.annual_savings_usd == pytest.approx(result.savings_usd * 365, abs=0.01)


def test_price_per_kwh_stored():
    result = compute_savings("Dishwasher", 1.0, 0.8, 0.20)
    assert result.price_per_kwh == 0.20


def test_device_type_stored():
    result = compute_savings("Water Heater", 3.0, 2.0, 0.12)
    assert result.device_type == "Water Heater"
