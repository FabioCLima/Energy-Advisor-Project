"""Tests for energy_advisor.services.forecasting."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from energy_advisor.services.forecasting import _WMO_CONDITION, generate_hourly_forecast

# Minimal valid Open-Meteo API response for mocking
_MOCK_API_RESPONSE = {
    "latitude": -23.5505,
    "longitude": -46.6333,
    "hourly": {
        "time": [f"2026-05-23T{h:02d}:00" for h in range(24)],
        "temperature_2m": [22.0 + h * 0.1 for h in range(24)],
        "relative_humidity_2m": [60] * 24,
        "wind_speed_10m": [3.0] * 24,
        "direct_radiation": [0.0] * 6 + [100.0 * i for i in range(1, 13)] + [0.0] * 6,
        "diffuse_radiation": [0.0] * 24,
        "weathercode": [0] * 24,
    },
}


def _mock_get_success(*args, **kwargs):
    mock = MagicMock()
    mock.json.return_value = _MOCK_API_RESPONSE
    mock.raise_for_status.return_value = None
    return mock


def _mock_get_failure(*args, **kwargs):
    raise ConnectionError("API unreachable")


# ── API path ─────────────────────────────────────────────────────────


def test_returns_24_hourly_entries():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    assert len(result["hourly"]) == 24


def test_api_path_uses_open_meteo_source():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    assert result["data_source"] == "open_meteo"


def test_days_returned_matches_request():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=3)
    assert result["forecast_days"] == 3


def test_days_clamped_to_valid_range():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        r_min = generate_hourly_forecast(location="São Paulo", days=0)   # clamps to 1
        r_max = generate_hourly_forecast(location="São Paulo", days=99)  # clamps to 7
    assert r_min["forecast_days"] == 1
    assert r_max["forecast_days"] == 7


def test_solar_irradiance_non_negative():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    for h in result["hourly"]:
        assert h["solar_irradiance"] >= 0.0, f"Irradiance at hour {h['hour']} is negative"


def test_nighttime_irradiance_zero_or_low():
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    hourly = {h["hour"]: h for h in result["hourly"]}
    assert hourly[0]["solar_irradiance"] < 50.0


def test_condition_in_allowed_values():
    """Condition must be one of the WMO mapping values (includes foggy, rain, etc.)."""
    valid = set(_WMO_CONDITION.values()) | {"partly_cloudy"}
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_success):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    for h in result["hourly"]:
        assert h["condition"] in valid, f"Unknown condition: {h['condition']}"


# ── Fallback path (API unreachable) ──────────────────────────────────


def test_fallback_on_api_failure():
    """When the API is unreachable, synthetic data is returned without raising."""
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_failure):
        result = generate_hourly_forecast(location="São Paulo", days=1)
    assert result["data_source"] == "synthetic"
    assert len(result["hourly"]) == 24


def test_fallback_preserves_location():
    """Fallback returns the location param unchanged."""
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_failure):
        result = generate_hourly_forecast(location="Tokyo", days=2)
    assert result["location"] == "Tokyo"
    assert result["forecast_days"] == 2


def test_fallback_is_deterministic():
    """Same location + same day must produce identical synthetic results."""
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_failure):
        r1 = generate_hourly_forecast(location="London", days=1)
        r2 = generate_hourly_forecast(location="London", days=1)
    assert r1["hourly"] == r2["hourly"]


def test_fallback_differs_by_location():
    """Different locations produce different synthetic data."""
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_failure):
        r1 = generate_hourly_forecast(location="London", days=1)
        r2 = generate_hourly_forecast(location="Sydney", days=1)
    assert r1["hourly"] != r2["hourly"]


def test_fallback_condition_in_allowed_values():
    valid = {"sunny", "partly_cloudy", "cloudy"}
    with patch("energy_advisor.services.forecasting.requests.get", side_effect=_mock_get_failure):
        result = generate_hourly_forecast(location="Miami", days=1)
    for h in result["hourly"]:
        assert h["condition"] in valid
