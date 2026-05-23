"""
Bootstrap step 2: Dados sintéticos — Persona João.

Persona:
  João — Desenvolvedor Python, 32 anos, São Paulo - SP
  - Home-office 5 dias/semana (seg–sex, 09h–18h)
  - Apartamento 70m², Distribuidora: Enel SP
  - Painel solar: 10 módulos 400W = 4kWp (orientação norte)
  - Veículo elétrico: Tesla Model 3 (carrega ter/qui/dom à noite)

Execução:
    python -m energy_advisor.bootstrap.sample_data
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager
from ..services.pricing import _BANDEIRA_DEFAULT, BANDEIRAS

# ── Estrutura de perfil de dispositivo ───────────────────────────────

class DeviceProfile(NamedTuple):
    device_type: str
    device_name: str
    location: str
    usage_pattern: str          # always_on | scheduled | presence_dependent
    kwh_lo: float
    kwh_hi: float
    prob_fn: Callable[[datetime], float]   # retorna probabilidade 0.0–1.0


# ── Constantes sazonais e tarifárias ─────────────────────────────────

# Probabilidade de uso do AC por mês em São Paulo (clima tropical)
_AC_PROB: dict[int, float] = {
    1: 0.85, 2: 0.85, 3: 0.70, 4: 0.40,
    5: 0.20, 6: 0.10, 7: 0.10, 8: 0.15,
    9: 0.35, 10: 0.60, 11: 0.75, 12: 0.85,
}

# Irradiância de pico por mês em São Paulo (W/m²)
_SOLAR_PEAK_W: dict[int, float] = {
    1: 980, 2: 950, 3: 850, 4: 750,
    5: 640, 6: 580, 7: 610, 8: 720,
    9: 810, 10: 880, 11: 950, 12: 980,
}

# Temperatura base por mês em São Paulo (°C)
_BASE_TEMP: dict[int, float] = {
    1: 27, 2: 27, 3: 25, 4: 22,
    5: 20, 6: 17, 7: 17, 8: 19,
    9: 21, 10: 23, 11: 25, 12: 27,
}

# Noites de carga do EV: terça=1, quinta=3, domingo=6  (weekday())
_EV_CHARGE_NIGHTS: frozenset[int] = frozenset({1, 3, 6})
_PANEL_KWP = 4.0   # kWp


def _is_ev_charging(dt: datetime) -> bool:
    """True se este timestamp é uma hora de carga do EV."""
    wd, h = dt.weekday(), dt.hour
    if wd in _EV_CHARGE_NIGHTS and h >= 22:
        return True
    prev = (wd - 1) % 7
    if prev in _EV_CHARGE_NIGHTS and h < 6:
        return True
    return False


def _hourly_rate_brl(dt: datetime) -> float:
    """Tarifa Enel SP em R$/kWh com bandeira ANEEL para o mês."""
    _, adicional = BANDEIRAS.get((dt.year, dt.month), _BANDEIRA_DEFAULT)
    if 18 <= dt.hour < 21:
        return 0.987 + adicional
    if dt.hour < 6:
        return 0.538 + adicional
    return 0.656 + adicional


# ── Perfis de dispositivos de João ───────────────────────────────────

_DEVICES: list[DeviceProfile] = [
    # ── Carga de base (always-on) ─────────────────────────────────────
    DeviceProfile(
        "appliance", "Geladeira Consul 400L", "kitchen", "always_on",
        kwh_lo=0.035, kwh_hi=0.065,
        prob_fn=lambda dt: 0.70,  # ciclo do compressor ~70%
    ),
    DeviceProfile(
        "network", "Roteador + Modem", "office", "always_on",
        kwh_lo=0.008, kwh_hi=0.012,
        prob_fn=lambda dt: 1.0,
    ),

    # ── Home-office (presence_dependent) ─────────────────────────────
    DeviceProfile(
        "computer", "PC Home-Office (Ryzen 7)", "office", "presence_dependent",
        kwh_lo=0.12, kwh_hi=0.22,
        prob_fn=lambda dt: 0.95 if dt.weekday() < 5 and 9 <= dt.hour < 18 else 0.0,
    ),
    DeviceProfile(
        "computer", "Monitor 27\" Dell UltraSharp", "office", "presence_dependent",
        kwh_lo=0.025, kwh_hi=0.045,
        prob_fn=lambda dt: 0.95 if dt.weekday() < 5 and 9 <= dt.hour < 18 else 0.0,
    ),
    DeviceProfile(
        "hvac", "AC Escritório Inverter 12k BTU", "office", "presence_dependent",
        kwh_lo=0.75, kwh_hi=1.30,
        prob_fn=lambda dt: (
            _AC_PROB.get(dt.month, 0.30)
            if dt.weekday() < 5 and 10 <= dt.hour < 17
            else 0.0
        ),
    ),

    # ── Entretenimento e iluminação (scheduled) ───────────────────────
    DeviceProfile(
        "entertainment", "Smart TV 55\" Samsung", "living_room", "scheduled",
        kwh_lo=0.08, kwh_hi=0.15,
        prob_fn=lambda dt: (
            0.85 if 19 <= dt.hour < 23
            else (0.75 if dt.weekday() >= 5 and 14 <= dt.hour < 18 else 0.0)
        ),
    ),
    DeviceProfile(
        "lighting", "Iluminação Sala (LED 6×9W)", "living_room", "scheduled",
        kwh_lo=0.020, kwh_hi=0.040,
        prob_fn=lambda dt: 0.90 if 18 <= dt.hour < 23 else 0.0,
    ),
    DeviceProfile(
        "lighting", "Iluminação Quarto (LED 3×7W)", "bedroom", "scheduled",
        kwh_lo=0.010, kwh_hi=0.025,
        prob_fn=lambda dt: 0.80 if (20 <= dt.hour < 23 or 6 <= dt.hour < 7) else 0.0,
    ),

    # ── Alto consumo (scheduled) ──────────────────────────────────────
    DeviceProfile(
        "appliance", "Chuveiro Elétrico 5500W", "bathroom", "scheduled",
        kwh_lo=3.0, kwh_hi=5.5,
        prob_fn=lambda dt: 0.80 if dt.hour in {6, 7, 19} else 0.0,
    ),
    DeviceProfile(
        "appliance", "Máquina de Lavar 11kg", "kitchen", "scheduled",
        kwh_lo=0.35, kwh_hi=0.65,
        prob_fn=lambda dt: (
            0.85 if dt.weekday() == 5 and dt.hour in {9, 10, 11}     # sábado
            else (0.12 if dt.weekday() < 5 and dt.hour in {10, 15} else 0.0)
        ),
    ),

    # ── Veículo elétrico (scheduled) ─────────────────────────────────
    DeviceProfile(
        "ev", "Tesla Model 3 Long Range", "outdoor", "scheduled",
        kwh_lo=4.5, kwh_hi=7.2,
        prob_fn=lambda dt: 0.95 if _is_ev_charging(dt) else 0.0,
    ),
]


# ── Geração solar ─────────────────────────────────────────────────────

def _generate_solar(dt: datetime, rng: random.Random) -> tuple[float, str, float, float] | None:
    """
    Retorna (generation_kwh, condition, temperature_c, irradiance) ou None (noite).
    Painel: 4kWp, São Paulo (-23.55°, orientação norte).
    """
    if not (6 <= dt.hour < 18):
        return None

    peak = _SOLAR_PEAK_W.get(dt.month, 750)
    # Gaussiana centrada ao meio-dia com σ=4h
    hour_factor = math.exp(-0.5 * ((dt.hour - 12) / 4.0) ** 2)

    conditions = ["ensolarado", "parcialmente_nublado", "nublado"]
    weights    = [0.55, 0.30, 0.15]
    condition  = rng.choices(conditions, weights=weights)[0]
    cloud      = {"ensolarado": 1.0, "parcialmente_nublado": 0.60, "nublado": 0.22}[condition]

    irradiance = peak * hour_factor * cloud + rng.uniform(-25, 25)
    irradiance = max(0.0, round(irradiance, 1))

    # Geração: (irradiance / 1000) × kWp × fator de perdas
    generation = irradiance / 1000.0 * _PANEL_KWP * rng.uniform(0.87, 1.0)

    temp = _BASE_TEMP.get(dt.month, 22) + rng.uniform(-3, 3)
    return round(generation, 3), condition, round(temp, 1), irradiance


# ── Ponto de entrada ──────────────────────────────────────────────────

def load_sample_data(
    settings: Settings | None = None,
    days: int = 90,
    seed: int = 42,
) -> None:
    """
    Popula o banco com 90 dias de dados sintéticos da persona João.
    Idempotente: pula se já existirem registros.

    Args:
        settings: Configurações opcionais.
        days: Dias de histórico a gerar (padrão 90).
        seed: Semente para reprodutibilidade.
    """
    settings = settings or Settings()
    db = DatabaseManager(db_path=settings.db_path)
    db.create_tables()

    if db.count_usage_records() > 0:
        logger.info(
            "Dados já presentes ({} registros de uso) — pulando geração.",
            db.count_usage_records(),
        )
        return

    rng = random.Random(seed)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    logger.info(
        "Gerando {} dias de dados para a persona João (seed={})...",
        days, seed,
    )
    usage_count = solar_count = 0

    current = start
    while current <= now:
        # ── Consumo por dispositivo ───────────────────────────────────
        for device in _DEVICES:
            prob = device.prob_fn(current)
            if prob > 0.0 and rng.random() < prob:
                kwh = round(rng.uniform(device.kwh_lo, device.kwh_hi), 3)
                cost = round(kwh * _hourly_rate_brl(current), 4)
                db.add_usage_record(
                    timestamp=current,
                    consumption_kwh=kwh,
                    device_type=device.device_type,
                    device_name=device.device_name,
                    usage_pattern=device.usage_pattern,
                    location=device.location,
                    cost_brl=cost,
                )
                usage_count += 1

        # ── Geração solar ─────────────────────────────────────────────
        solar = _generate_solar(current, rng)
        if solar is not None:
            generation, condition, temp, irradiance = solar
            db.add_generation_record(
                timestamp=current,
                generation_kwh=generation,
                weather_condition=condition,
                temperature_c=temp,
                solar_irradiance=irradiance,
            )
            solar_count += 1

        current += timedelta(hours=1)

    logger.info(
        "Dados carregados: {} registros de consumo, {} registros solares ({} dias).",
        usage_count, solar_count, days,
    )


if __name__ == "__main__":
    load_sample_data()
