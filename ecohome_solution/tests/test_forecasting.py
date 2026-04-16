"""Tests for energy_advisor.services.forecasting."""
from __future__ import annotations

from energy_advisor.services.forecasting import generate_hourly_forecast


def test_returns_24_hourly_entries():
    result = generate_hourly_forecast(location="Berlin", days=1)
    assert len(result["hourly"]) == 24


def test_deterministic_output():
    """Same location + same date must produce identical results."""
    r1 = generate_hourly_forecast(location="London", days=3)
    r2 = generate_hourly_forecast(location="London", days=3)
    assert r1["hourly"] == r2["hourly"]


def test_different_locations_differ():
    r1 = generate_hourly_forecast(location="London", days=1)
    r2 = generate_hourly_forecast(location="Sydney", days=1)
    assert r1["hourly"] != r2["hourly"]


def test_solar_irradiance_non_negative():
    result = generate_hourly_forecast(location="Lisbon", days=1)
    for h in result["hourly"]:
        assert h["solar_irradiance"] >= 0.0, f"Irradiance at hour {h['hour']} is negative"


def test_nighttime_irradiance_zero_or_low():
    result = generate_hourly_forecast(location="London", days=1)
    hourly = {h["hour"]: h for h in result["hourly"]}
    # At midnight (hour 0) irradiance should be very close to 0
    assert hourly[0]["solar_irradiance"] < 50.0


def test_days_clamped_to_valid_range():
    r_min = generate_hourly_forecast(location="Paris", days=0)   # should clamp to 1
    r_max = generate_hourly_forecast(location="Paris", days=99)  # should clamp to 7
    assert r_min["forecast_days"] == 1
    assert r_max["forecast_days"] == 7


def test_condition_in_allowed_values():
    result = generate_hourly_forecast(location="Miami", days=1)
    for h in result["hourly"]:
        assert h["condition"] in {"sunny", "partly_cloudy", "cloudy"}


def test_location_and_days_in_result():
    result = generate_hourly_forecast(location="Tokyo", days=2)
    assert result["location"] == "Tokyo"
    assert result["forecast_days"] == 2
