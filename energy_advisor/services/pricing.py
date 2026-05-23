from __future__ import annotations

from datetime import datetime

# ── Bandeiras tarifárias ANEEL (R$/kWh adicional) ────────────────────
# Publicadas mensalmente pelo CCEE. Fonte: ANEEL resolução homologatória.
BANDEIRAS: dict[tuple[int, int], tuple[str, float]] = {
    # (ano, mês): (nome, adicional R$/kWh)
    (2026, 2): ("vermelha_1", 0.03971),
    (2026, 3): ("amarela",    0.01885),
    (2026, 4): ("verde",      0.00000),
    (2026, 5): ("verde",      0.00000),
}
_BANDEIRA_DEFAULT = ("verde", 0.00000)

# ── Enel SP — tarifa residencial (valores aproximados 2025) ───────────
# Fonte: Enel São Paulo — Tabela de Tarifas Residencial B1
_FORA_PONTA_NOTURNO = 0.538   # 0h–5h  (R$/kWh, sem bandeira)
_FORA_PONTA_DIURNO  = 0.656   # 6h–17h e 21h–23h
_HORA_DE_PONTA      = 0.987   # 18h–20h (hora de ponta ANEEL, dias úteis)


def get_bandeira(date: datetime) -> tuple[str, float]:
    """Retorna (nome_bandeira, adicional_R$/kWh) para uma data."""
    return BANDEIRAS.get((date.year, date.month), _BANDEIRA_DEFAULT)


def generate_time_of_use_prices(date: str | None = None) -> dict:
    """
    Gera a tabela de preços TOU Enel SP com bandeira tarifária ANEEL.

    Períodos:
      - off_peak  : 0h–5h   (fora de ponta noturno — melhor janela para EV)
      - mid_peak  : 6h–17h e 21h–23h (fora de ponta diurno)
      - peak      : 18h–20h (hora de ponta ANEEL)

    Returns dict compatível com ElectricityPrices schema.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    dt = datetime.strptime(date, "%Y-%m-%d")
    bandeira_nome, bandeira_adicional = get_bandeira(dt)

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

        hourly_rates.append({
            "hour": hour,
            "rate": round(base + bandeira_adicional, 4),
            "period": period,
            "demand_charge": round(demand_charge, 4),
        })

    return {
        "date": date,
        "pricing_type": "time_of_use",
        "currency": "BRL",
        "unit": "per_kWh",
        "bandeira": bandeira_nome,
        "distribuidora": "Enel SP",
        "bandeira_adicional_brl": bandeira_adicional,
        "hourly_rates": hourly_rates,
    }
