from __future__ import annotations

from datetime import datetime

from ..config import Settings
from .aneel_client import resolve_bandeira

_FORA_PONTA_NOTURNO = 0.538
_FORA_PONTA_DIURNO = 0.656
_HORA_DE_PONTA = 0.987


def get_bandeira(date: datetime) -> tuple[str, float]:
    settings = Settings()
    resolution = resolve_bandeira(
        date,
        cache_path=settings.aneel_cache_path,
        fetch_enabled=settings.aneel_fetch_enabled,
        allow_insecure_ssl=settings.aneel_allow_insecure_ssl,
    )
    return resolution.bandeira, resolution.adicional_brl


def generate_time_of_use_prices(date: str | None = None) -> dict:
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    dt = datetime.strptime(date, "%Y-%m-%d")
    settings = Settings()
    resolution = resolve_bandeira(
        dt,
        cache_path=settings.aneel_cache_path,
        fetch_enabled=settings.aneel_fetch_enabled,
        allow_insecure_ssl=settings.aneel_allow_insecure_ssl,
    )

    hourly_rates: list[dict] = []
    for hour in range(24):
        if 18 <= hour < 21:
            period = "peak"
            base = _HORA_DE_PONTA
            demand_charge = 0.08
        elif hour < 6:
            period = "off_peak"
            base = _FORA_PONTA_NOTURNO
            demand_charge = 0.0
        else:
            period = "mid_peak"
            base = _FORA_PONTA_DIURNO
            demand_charge = 0.0

        hourly_rates.append(
            {
                "hour": hour,
                "rate": round(base + resolution.adicional_brl, 4),
                "period": period,
                "demand_charge": round(demand_charge, 4),
            }
        )

    return {
        "date": date,
        "pricing_type": "time_of_use",
        "currency": "BRL",
        "unit": "per_kWh",
        "bandeira": resolution.bandeira,
        "distribuidora": "Enel SP",
        "bandeira_adicional_brl": resolution.adicional_brl,
        "data_source": resolution.data_source,
        "fetched_at": resolution.fetched_at,
        "fallback_used": resolution.fallback_used,
        "hourly_rates": hourly_rates,
    }
