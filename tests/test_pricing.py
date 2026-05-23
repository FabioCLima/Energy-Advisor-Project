"""Tests for energy_advisor.services.pricing — tarifas Enel SP em BRL."""
from __future__ import annotations

from datetime import datetime

import pytest
from energy_advisor.services.pricing import generate_time_of_use_prices


def test_returns_24_hourly_rates():
    result = generate_time_of_use_prices()
    assert result["pricing_type"] == "time_of_use"
    assert len(result["hourly_rates"]) == 24


def test_currency_is_brl():
    result = generate_time_of_use_prices()
    assert result["currency"] == "BRL"
    assert result["distribuidora"] == "Enel SP"


def test_off_peak_hours():
    # Fora de ponta noturno: 0h–5h — melhor janela para EV
    result = generate_time_of_use_prices(date="2026-04-15")  # bandeira verde
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    for h in range(0, 6):
        assert rates[h]["period"] == "off_peak", f"Hour {h} should be off_peak"
        assert rates[h]["rate"] < 0.60, f"Off-peak rate at {h}h should be < R$0.60"


def test_peak_hours():
    # Hora de ponta ANEEL: 18h–20h
    result = generate_time_of_use_prices(date="2026-04-15")
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    for h in range(18, 21):
        assert rates[h]["period"] == "peak", f"Hour {h} should be peak"
        assert rates[h]["rate"] > 0.90, f"Peak rate at {h}h should be > R$0.90"
        assert rates[h]["demand_charge"] > 0.0


def test_mid_peak_hours():
    result = generate_time_of_use_prices(date="2026-04-15")
    rates = {r["hour"]: r for r in result["hourly_rates"]}
    mid_hours = list(range(6, 18)) + [21, 22, 23]
    for h in mid_hours:
        assert rates[h]["period"] == "mid_peak", f"Hour {h} should be mid_peak"


def test_bandeira_verde_sem_adicional():
    result = generate_time_of_use_prices(date="2026-04-15")
    assert result["bandeira"] == "verde"
    assert result["bandeira_adicional_brl"] == 0.0


def test_bandeira_vermelha_aumenta_tarifa():
    result_verde    = generate_time_of_use_prices(date="2026-04-15")  # verde
    result_vermelha = generate_time_of_use_prices(date="2026-02-15")  # vermelha_1
    rate_verde    = result_verde["hourly_rates"][10]["rate"]
    rate_vermelha = result_vermelha["hourly_rates"][10]["rate"]
    assert rate_vermelha > rate_verde
    assert result_vermelha["bandeira"] == "vermelha_1"


def test_bandeira_amarela():
    result = generate_time_of_use_prices(date="2026-03-10")
    assert result["bandeira"] == "amarela"
    assert result["bandeira_adicional_brl"] == pytest.approx(0.01885, abs=0.0001)


def test_date_defaults_to_today():
    result = generate_time_of_use_prices()
    assert result["date"] == datetime.now().strftime("%Y-%m-%d")


def test_explicit_date():
    result = generate_time_of_use_prices(date="2026-05-01")
    assert result["date"] == "2026-05-01"


def test_all_rates_positive():
    result = generate_time_of_use_prices()
    for r in result["hourly_rates"]:
        assert r["rate"] > 0, f"Rate at hour {r['hour']} should be positive"


