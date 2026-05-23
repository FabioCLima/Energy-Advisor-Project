"""
Visualization components for the EcoHome Energy Advisor dashboard.
All public functions return Plotly figures ready for st.plotly_chart().
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.pricing import generate_time_of_use_prices

# Color palette by usage pattern
_PATTERN_COLOR = {
    "always_on":          "#3498DB",
    "presence_dependent": "#E67E22",
    "scheduled":          "#2ECC71",
}
_PATTERN_LABEL = {
    "always_on":          "Base load",
    "presence_dependent": "Home office",
    "scheduled":          "Scheduled",
}
_PERIOD_LABEL = {
    "off_peak": "Off-peak (night)",
    "mid_peak": "Mid-peak",
    "peak":     "Peak (hora de ponta)",
}


@st.cache_data(ttl=300)
def _load_usage(db_path: str, days: int) -> pd.DataFrame:
    db = DatabaseManager(db_path=db_path)
    end = datetime.now()
    start = end - timedelta(days=days)
    records = db.get_usage_by_date_range(start, end)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([{
        "timestamp":     r.timestamp,
        "hour":          r.timestamp.hour,
        "weekday":       r.timestamp.weekday(),
        "device_name":   r.device_name,
        "device_type":   r.device_type,
        "usage_pattern": r.usage_pattern or "scheduled",
        "location":      r.location or "other",
        "kwh":           r.consumption_kwh,
        "cost_brl":      r.cost_brl or 0.0,
    } for r in records])


@st.cache_data(ttl=300)
def _load_solar(db_path: str, days: int) -> pd.DataFrame:
    db = DatabaseManager(db_path=db_path)
    end = datetime.now()
    start = end - timedelta(days=days)
    records = db.get_generation_by_date_range(start, end)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([{
        "timestamp":  r.timestamp,
        "hour":       r.timestamp.hour,
        "kwh":        r.generation_kwh,
        "condition":  r.weather_condition,
        "irradiance": r.solar_irradiance or 0.0,
    } for r in records])


# ── Metrics row ───────────────────────────────────────────────────────

def render_metrics(db_path: str, days: int = 30) -> None:
    df_usage = _load_usage(db_path, days)
    df_solar = _load_solar(db_path, days)

    total_kwh  = df_usage["kwh"].sum()      if not df_usage.empty else 0.0
    total_brl  = df_usage["cost_brl"].sum() if not df_usage.empty else 0.0
    solar_kwh  = df_solar["kwh"].sum()      if not df_solar.empty else 0.0
    office_brl = (
        df_usage[df_usage["location"] == "office"]["cost_brl"].sum()
        if not df_usage.empty else 0.0
    )

    cols = st.columns(4)
    cols[0].metric("⚡ Total Consumption", f"{total_kwh:,.0f} kWh",  help=f"Last {days} days")
    cols[1].metric("💸 Total Cost",        f"R$ {total_brl:,.2f}",   help=f"Last {days} days")
    cols[2].metric("☀️ Solar Generation",  f"{solar_kwh:,.0f} kWh",  help=f"4kWp panel — {days} days")
    cols[3].metric("🖥️ Home Office Cost",  f"R$ {office_brl:,.2f}",  help="PC + Monitor + AC office")


# ── Chart 1: Consumption by device ───────────────────────────────────

def chart_consumption_by_device(db_path: str, days: int = 30) -> go.Figure:
    df = _load_usage(db_path, days)
    if df.empty:
        return go.Figure().update_layout(title="No data available")

    agg = (
        df.groupby(["device_name", "usage_pattern"], as_index=False)
          .agg(kwh=("kwh", "sum"), cost_brl=("cost_brl", "sum"))
          .sort_values("kwh", ascending=True)
    )
    agg["pattern_label"] = agg["usage_pattern"].map(_PATTERN_LABEL)

    fig = px.bar(
        agg, x="kwh", y="device_name", orientation="h",
        color="pattern_label",
        color_discrete_map={v: _PATTERN_COLOR[k] for k, v in _PATTERN_LABEL.items()},
        hover_data={"cost_brl": ":.2f", "kwh": ":.1f"},
        labels={
            "kwh":           "Consumption (kWh)",
            "device_name":   "",
            "pattern_label": "Category",
            "cost_brl":      "Cost (R$)",
        },
        title=f"Consumption by Device — last {days} days",
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=10, r=20, t=60, b=20),
    )
    return fig


# ── Chart 2: Solar generation vs consumption (hourly average) ─────────

def chart_solar_vs_consumption(db_path: str, days: int = 30) -> go.Figure:
    df_usage = _load_usage(db_path, days)
    df_solar = _load_solar(db_path, days)
    n_days   = max(days, 1)

    usage_by_hour = (
        df_usage.groupby("hour")["kwh"].sum() / n_days
        if not df_usage.empty else pd.Series(0.0, index=range(24))
    )
    solar_by_hour = (
        df_solar.groupby("hour")["kwh"].sum() / n_days
        if not df_solar.empty else pd.Series(0.0, index=range(24))
    )

    hours      = list(range(24))
    usage_vals = [usage_by_hour.get(h, 0.0) for h in hours]
    solar_vals = [solar_by_hour.get(h, 0.0) for h in hours]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=usage_vals, name="Consumption",
        fill="tozeroy", line=dict(color="#E74C3C", width=2),
        fillcolor="rgba(231,76,60,0.15)",
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=solar_vals, name="Solar Generation",
        fill="tozeroy", line=dict(color="#F39C12", width=2),
        fillcolor="rgba(243,156,18,0.20)",
    ))
    fig.update_layout(
        title=f"Solar vs Consumption — hourly average ({days} days)",
        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
        yaxis=dict(title="avg kWh"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(l=10, r=20, t=60, b=40),
    )
    return fig


# ── Chart 3: TOU tariff bar chart ────────────────────────────────────

def chart_tou_rates(date: str | None = None) -> go.Figure:
    pricing  = generate_time_of_use_prices(date)
    rates    = pricing["hourly_rates"]
    bandeira = pricing["bandeira"].replace("_", " ").title()
    adicional = pricing["bandeira_adicional_brl"]

    hours   = [r["hour"]   for r in rates]
    tariffs = [r["rate"]   for r in rates]
    periods = [r["period"] for r in rates]

    fig = go.Figure(go.Bar(
        x=hours,
        y=tariffs,
        marker_color=[
            "#27AE60" if p == "off_peak" else
            "#F39C12" if p == "mid_peak" else
            "#E74C3C"
            for p in periods
        ],
        text=[f"R${t:.3f}" for t in tariffs],
        textposition="outside",
        hovertext=[
            f"{_PERIOD_LABEL.get(p, p)}<br>R$ {t:.4f}/kWh"
            for p, t in zip(periods, tariffs)
        ],
        hoverinfo="text",
    ))

    adicional_txt = f" (+R$ {adicional:.4f}/kWh surcharge)" if adicional > 0 else ""
    fig.update_layout(
        title=f"Enel SP Tariffs — Bandeira {bandeira}{adicional_txt}",
        xaxis=dict(title="Hour", tickmode="linear", dtick=1),
        yaxis=dict(title="R$/kWh", range=[0, max(tariffs) * 1.25]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=340,
        margin=dict(l=10, r=20, t=60, b=40),
        showlegend=False,
    )
    return fig


# ── Chart 4: Home office cost report ─────────────────────────────────

_OFFICE_DEVICES = [
    "PC Home-Office (Ryzen 7)",
    "Monitor 27\" Dell UltraSharp",
    "AC Escritório Inverter 12k BTU",
]

def chart_home_office_report(db_path: str, days: int = 30) -> tuple[go.Figure, dict]:
    df = _load_usage(db_path, days)
    if df.empty:
        return go.Figure(), {}

    df_office = df[df["device_name"].isin(_OFFICE_DEVICES)]
    agg = (
        df_office.groupby("device_name", as_index=False)
                 .agg(kwh=("kwh", "sum"), cost_brl=("cost_brl", "sum"))
    )

    total_brl   = agg["cost_brl"].sum()
    monthly_brl = total_brl / (days / 30)
    annual_brl  = monthly_brl * 12

    fig = px.bar(
        agg, x="device_name", y="cost_brl",
        color="device_name",
        color_discrete_sequence=["#3498DB", "#9B59B6", "#E67E22"],
        labels={"device_name": "", "cost_brl": "Cost (R$)"},
        title=f"Home Office Cost — last {days} days",
        text_auto=".2f",
    )
    fig.update_traces(texttemplate="R$ %{text}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=340,
        margin=dict(l=10, r=20, t=60, b=40),
        yaxis=dict(title="R$"),
    )

    summary = {
        "period_days": days,
        "total_brl":   round(total_brl, 2),
        "monthly_brl": round(monthly_brl, 2),
        "annual_brl":  round(annual_brl, 2),
        "total_kwh":   round(agg["kwh"].sum(), 1),
    }
    return fig, summary
