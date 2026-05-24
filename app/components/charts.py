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
from energy_advisor.services.forecast_router import route_usage_forecast
from energy_advisor.services.forecasting import generate_hourly_forecast
from energy_advisor.services.pricing import generate_time_of_use_prices
from energy_advisor.services.usage_forecasting import (
    UsageForecastParams,
    load_hourly_usage_series,
    seasonal_naive_usage_forecast,
)

# ── Constants ─────────────────────────────────────────────────────────

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
    "off_peak": "Off-peak night",
    "mid_peak": "Mid-peak",
    "peak":     "Peak (hora de ponta)",
}

# Devices that belong to home office — single source of truth (fixes B1)
HOME_OFFICE_DEVICES = frozenset({
    "PC Home-Office (Ryzen 7)",
    'Monitor 27" Dell UltraSharp',
    "AC Escritório Inverter 12k BTU",
})

_DISPLAY_NAME = {
    "AC Escritório Inverter 12k BTU": "Office AC",
    "Chuveiro Elétrico 5500W": "Electric Shower",
    "Geladeira Consul 400L": "Fridge",
    "Iluminação Quarto (LED 3×7W)": "Bedroom Lights",
    "Iluminação Sala (LED 6×9W)": "Living Room Lights",
    'Monitor 27" Dell UltraSharp': "Monitor",
    "Máquina de Lavar 11kg": "Washing Machine",
    "PC Home-Office (Ryzen 7)": "Workstation",
    "Roteador + Modem": "Router + Modem",
    'Smart TV 55" Samsung': "Smart TV",
    "Tesla Model 3 Long Range": "Tesla Model 3",
}


def _friendly_device_name(name: str) -> str:
    return _DISPLAY_NAME.get(name, name)


def _delta_pct(current: float, previous: float) -> str | None:
    if previous <= 0:
        return None
    pct = ((current - previous) / previous) * 100
    sign = "-" if pct < 0 else ""
    return f"{sign}{abs(pct):.0f}% vs prev"


def _split_current_previous(df: pd.DataFrame, days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df
    cutoff = _day_start(days)
    current = df[df["timestamp"] >= cutoff]
    previous = df[(df["timestamp"] < cutoff) & (df["timestamp"] >= _day_start(days * 2))]
    return current, previous


def _format_freshness(dt: pd.Timestamp | datetime | None) -> str:
    if dt is None or pd.isna(dt):
        return "no recent update"
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    return dt.strftime("%d %b %Y · %H:%M")


def build_dashboard_export_csv(db_path: str, days: int = 30) -> bytes:
    """Return a compact CSV export with KPI and per-device summaries."""
    df_usage = _load_usage(db_path, days)
    df_solar = _load_solar(db_path, days)
    usage_rows = []
    if not df_usage.empty:
        usage_rows = (
            df_usage.groupby("device_name", as_index=False)
            .agg(consumption_kwh=("kwh", "sum"), cost_brl=("cost_brl", "sum"))
            .assign(section="device_summary")
        )
        usage_rows["device_name"] = usage_rows["device_name"].map(_friendly_device_name)
    total_kwh = df_usage["kwh"].sum() if not df_usage.empty else 0.0
    total_brl = df_usage["cost_brl"].sum() if not df_usage.empty else 0.0
    solar_kwh = df_solar["kwh"].sum() if not df_solar.empty else 0.0
    summary = pd.DataFrame([
        {"section": "kpi_summary", "metric": "analysis_days", "value": days},
        {"section": "kpi_summary", "metric": "total_consumption_kwh", "value": round(total_kwh, 3)},
        {"section": "kpi_summary", "metric": "gross_cost_brl", "value": round(total_brl, 2)},
        {"section": "kpi_summary", "metric": "solar_generation_kwh", "value": round(solar_kwh, 3)},
    ])
    device_df = pd.DataFrame(usage_rows) if len(usage_rows) else pd.DataFrame(columns=["section", "device_name", "consumption_kwh", "cost_brl"])
    out = pd.concat([summary, device_df], ignore_index=True, sort=False)
    return out.to_csv(index=False).encode("utf-8")


def render_top_consumers(db_path: str, days: int = 30) -> None:
    df = _load_usage(db_path, days)
    if df.empty:
        return
    df = df[~df["is_ev"]]
    if df.empty:
        return
    agg = (
        df.groupby("device_name", as_index=False)["kwh"]
        .sum()
        .sort_values("kwh", ascending=False)
        .head(3)
    )
    total = max(df["kwh"].sum(), 1e-9)
    cols = st.columns(3, gap="medium")
    for col, row in zip(cols, agg.itertuples(index=False), strict=False):
        pct = row.kwh / total * 100
        label = _friendly_device_name(row.device_name)
        compact_label = label.replace("Electric Shower", "Shower").replace("Office AC", "Office AC")
        col.metric(
            compact_label,
            f"{row.kwh:.0f} kWh",
            f"{pct:.0f}% of non-EV",
            help=f"{label} consumed {row.kwh:.1f} kWh in this period.",
        )


_AVG_RATE_BRL = 0.656   # Enel SP mid-peak base rate used for solar savings estimate

# João's solar panel — used in forecast conversion
_PANEL_KWP = 4.0    # installed capacity (10 × 400W modules)
_PANEL_EFF = 0.85   # derating: inverter losses + temperature + dust


# ── Data loaders (cached) ─────────────────────────────────────────────

@st.cache_data(ttl=1800)
def _load_weather() -> dict:
    """Fetch today's hourly forecast — cached 30 min to avoid hammering Open-Meteo."""
    return generate_hourly_forecast("São Paulo", days=1)


def _day_start(days_ago: int) -> datetime:
    """Midnight N days ago — matches the agent's YYYY-MM-DD date boundary."""
    return (datetime.now() - timedelta(days=days_ago)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


@st.cache_data(ttl=300)
def _load_usage(db_path: str, days: int) -> pd.DataFrame:
    db = DatabaseManager(db_path=db_path)
    records = db.get_usage_by_date_range(
        _day_start(days), datetime.now()
    )
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
        "is_ev":         r.device_type == "ev",
        "is_office":     r.device_name in HOME_OFFICE_DEVICES,
    } for r in records])


@st.cache_data(ttl=300)
def _load_solar(db_path: str, days: int) -> pd.DataFrame:
    db = DatabaseManager(db_path=db_path)
    records = db.get_generation_by_date_range(
        _day_start(days), datetime.now()
    )
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
    """Themed KPI groups with previous-period deltas and freshness metadata."""
    df_usage_all = _load_usage(db_path, max(days * 2, days))
    df_solar_all = _load_solar(db_path, max(days * 2, days))
    df_usage, df_usage_prev = _split_current_previous(df_usage_all, days)
    df_solar, df_solar_prev = _split_current_previous(df_solar_all, days)

    total_kwh = df_usage["kwh"].sum() if not df_usage.empty else 0.0
    total_brl = df_usage["cost_brl"].sum() if not df_usage.empty else 0.0
    solar_kwh = df_solar["kwh"].sum() if not df_solar.empty else 0.0
    office_brl = df_usage[df_usage["is_office"]]["cost_brl"].sum() if not df_usage.empty else 0.0
    ev_kwh = df_usage[df_usage["is_ev"]]["kwh"].sum() if not df_usage.empty else 0.0

    prev_total_kwh = df_usage_prev["kwh"].sum() if not df_usage_prev.empty else 0.0
    prev_total_brl = df_usage_prev["cost_brl"].sum() if not df_usage_prev.empty else 0.0
    prev_solar_kwh = df_solar_prev["kwh"].sum() if not df_solar_prev.empty else 0.0
    prev_office_brl = df_usage_prev[df_usage_prev["is_office"]]["cost_brl"].sum() if not df_usage_prev.empty else 0.0
    prev_ev_kwh = df_usage_prev[df_usage_prev["is_ev"]]["kwh"].sum() if not df_usage_prev.empty else 0.0

    self_suff = (solar_kwh / total_kwh * 100) if total_kwh > 0 else 0.0
    prev_self_suff = (prev_solar_kwh / prev_total_kwh * 100) if prev_total_kwh > 0 else 0.0
    solar_savings = solar_kwh * _AVG_RATE_BRL
    prev_solar_savings = prev_solar_kwh * _AVG_RATE_BRL
    net_cost = max(0.0, total_brl - solar_savings)
    prev_net_cost = max(0.0, prev_total_brl - prev_solar_savings)
    ev_share = (ev_kwh / total_kwh * 100) if total_kwh > 0 else 0.0
    prev_ev_share = (prev_ev_kwh / prev_total_kwh * 100) if prev_total_kwh > 0 else 0.0

    latest_usage = df_usage["timestamp"].max() if not df_usage.empty else None
    latest_solar = df_solar["timestamp"].max() if not df_solar.empty else None
    freshest = max([ts for ts in [latest_usage, latest_solar] if ts is not None], default=None)

    st.caption(
        f"Analysis window: {days} days · compare against previous {days} days · "
        f"latest data: {_format_freshness(freshest)}"
    )

    st.markdown("**Financial**")
    row_fin = st.columns(3)
    row_fin[0].metric("💸 Gross Cost", f"R$ {total_brl:,.2f}", _delta_pct(total_brl, prev_total_brl), help="Before solar offset")
    row_fin[1].metric("☀️ Solar Savings", f"R$ {solar_savings:,.2f}", _delta_pct(solar_savings, prev_solar_savings), help=f"Solar × R$ {_AVG_RATE_BRL}/kWh")
    row_fin[2].metric("🔌 Net Grid Cost", f"R$ {net_cost:,.2f}", _delta_pct(net_cost, prev_net_cost), help="Gross cost − solar savings")

    st.markdown("**Energy**")
    row_energy = st.columns(3)
    row_energy[0].metric("⚡ Consumption", f"{total_kwh:,.0f} kWh", _delta_pct(total_kwh, prev_total_kwh), help=f"Last {days} days")
    row_energy[1].metric("☀️ Solar Generation", f"{solar_kwh:,.0f} kWh", _delta_pct(solar_kwh, prev_solar_kwh), help=f"4kWp panel — last {days} days")
    row_energy[2].metric("🔋 Self-sufficiency", f"{self_suff:.0f}%", _delta_pct(self_suff, prev_self_suff), help="Solar ÷ total consumption")

    st.markdown("**Efficiency**")
    row_eff = st.columns(2)
    row_eff[0].metric("🖥️ Home Office Cost", f"R$ {office_brl:,.2f}", _delta_pct(office_brl, prev_office_brl), help="PC + Monitor + Office AC")
    row_eff[1].metric("🚗 EV Share", f"{ev_share:.0f}%", _delta_pct(ev_share, prev_ev_share), help="EV consumption ÷ total household consumption")


# ── Chart 1: Consumption by device (EV excluded — see EV section) ─────

def chart_consumption_by_device(db_path: str, days: int = 30) -> go.Figure:
    """
    Horizontal bar chart excluding EV charger (D1 fix).
    Adds % of total as bar label (D2 fix).
    """
    df = _load_usage(db_path, days)
    if df.empty:
        return go.Figure().update_layout(title="No data available")

    df_no_ev = df[~df["is_ev"]]
    total_kwh = df_no_ev["kwh"].sum()

    agg = (
        df_no_ev
        .groupby(["device_name", "usage_pattern"], as_index=False)
        .agg(kwh=("kwh", "sum"), cost_brl=("cost_brl", "sum"))
        .sort_values("kwh", ascending=True)
    )
    agg["pattern_label"] = agg["usage_pattern"].map(_PATTERN_LABEL)
    agg["display_name"]  = agg["device_name"].map(_friendly_device_name)
    agg["pct"]           = (agg["kwh"] / total_kwh * 100).round(1)
    agg["label"]         = agg["pct"].apply(lambda v: "<1%" if 0 < v < 1 else f"{v:.0f}%")

    max_kwh = max(float(agg["kwh"].max()), 1.0)

    fig = px.bar(
        agg,
        x="kwh",
        y="display_name",
        orientation="h",
        color="pattern_label",
        color_discrete_map={v: _PATTERN_COLOR[k] for k, v in _PATTERN_LABEL.items()},
        text="label",
        hover_data={"cost_brl": ":.2f", "kwh": ":.1f", "pct": ":.1f"},
        labels={
            "kwh":           "Consumption (kWh)",
            "display_name":  "",
            "pattern_label": "Category",
            "cost_brl":      "Cost (R$)",
            "pct":           "% of total",
        },
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis=dict(range=[0, max_kwh * 1.15], title="Consumption (kWh)", gridcolor="rgba(148,163,184,0.18)"),
        yaxis=dict(title="", automargin=True),
        legend=dict(
            title="",
            orientation="h",
            yanchor="top",
            y=-0.24,
            xanchor="left",
            x=0,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=max(390, 110 + len(agg) * 31),
        margin=dict(l=12, r=88, t=16, b=92),
        uniformtext=dict(minsize=10, mode="show"),
    )
    return fig


# ── EV summary card (D1 — Tesla separated) ───────────────────────────

def render_ev_summary(db_path: str, days: int = 30) -> None:
    """Render EV stats as metric cards instead of a distorted bar."""
    df = _load_usage(db_path, days)
    if df.empty:
        return
    ev = df[df["is_ev"]]
    if ev.empty:
        return

    sessions = (
        ev.groupby(ev["timestamp"].dt.date)["kwh"].sum()
        .pipe(lambda s: s[s > 0])
        .count()
    )
    total_kwh  = ev["kwh"].sum()
    total_brl  = ev["cost_brl"].sum()
    avg_cost   = total_brl / sessions if sessions > 0 else 0.0
    pct_total  = total_kwh / df["kwh"].sum() * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚗 EV Total Consumption",  f"{total_kwh:,.0f} kWh")
    c2.metric("💰 EV Total Cost",         f"R$ {total_brl:,.2f}")
    c3.metric("📅 Charging Days",         f"{sessions}")
    c4.metric("📊 % of Home Consumption", f"{pct_total:.0f}%")
    st.caption(
        f"Average cost per charging day: R$ {avg_cost:.2f} · "
        "Best charging window: **0h–5h (off-peak, R$ 0.538/kWh)**"
    )


# ── Chart 2: Solar vs Consumption with surplus highlight (S1, S2) ─────

def chart_solar_vs_consumption(db_path: str, days: int = 30) -> go.Figure:
    """
    Area chart with solar surplus highlighted in green (S2).
    Y-axis labeled as kW avg (S1 fix).
    """
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

    # Consumption area
    fig.add_trace(go.Scatter(
        x=hours, y=usage_vals, name="Consumption",
        fill="tozeroy", line=dict(color="#E74C3C", width=2),
        fillcolor="rgba(231,76,60,0.15)",
    ))

    # Solar generation area
    fig.add_trace(go.Scatter(
        x=hours, y=solar_vals, name="Solar Generation",
        fill="tozeroy", line=dict(color="#F39C12", width=2),
        fillcolor="rgba(243,156,18,0.20)",
    ))

    surplus_y = [max(0.0, s - u) for s, u in zip(solar_vals, usage_vals, strict=True)]
    import_y = [max(0.0, u - s) for s, u in zip(solar_vals, usage_vals, strict=True)]
    surplus_base = [min(s, u) for s, u in zip(solar_vals, usage_vals, strict=True)]
    fig.add_trace(go.Scatter(
        x=hours + hours[::-1],
        y=[b + s for b, s in zip(surplus_base, surplus_y, strict=True)] + surplus_base[::-1],
        fill="toself",
        fillcolor="rgba(46, 204, 113, 0.28)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Solar Surplus → Grid",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Bar(
        x=hours,
        y=import_y,
        name="Grid Import",
        marker_color="rgba(52, 152, 219, 0.35)",
        opacity=0.75,
    ))

    # Current hour marker
    now_h = datetime.now().hour
    fig.add_vline(
        x=now_h, line_width=1.5, line_dash="dot", line_color="#7F8C8D",
        annotation_text=f"Now ({now_h}h)",
        annotation_position="top right",
        annotation_font_size=11,
    )

    fig.update_layout(
        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2, gridcolor="rgba(148,163,184,0.16)"),
        yaxis=dict(title="kW avg", gridcolor="rgba(148,163,184,0.18)", rangemode="tozero"),
        legend=dict(
            title="",
            orientation="h",
            yanchor="top",
            y=-0.24,
            xanchor="left",
            x=0,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(l=18, r=28, t=18, b=92),
    )
    return fig


# ── Chart 3: TOU energy rates (T1, T2) ───────────────────────────────

def chart_tou_rates(date: str | None = None) -> go.Figure:
    """
    Bar chart of hourly energy rates.
    Shows label only on first bar of each period (T1).
    Adds vertical 'Now' line (T2).
    """
    pricing   = generate_time_of_use_prices(date)
    rates     = pricing["hourly_rates"]
    bandeira  = pricing["bandeira"].replace("_", " ").title()
    adicional = pricing["bandeira_adicional_brl"]

    hours   = [r["hour"]   for r in rates]
    rate_values = [r["rate"]   for r in rates]
    periods = [r["period"] for r in rates]

    # T1: label only on first bar of each period group
    texts, seen = [], set()
    for p, t in zip(periods, rate_values, strict=True):
        if p not in seen:
            texts.append(f"R${t:.3f}")
            seen.add(p)
        else:
            texts.append("")

    current_colors = [
        "#1E8449" if p == "off_peak" else
        "#D68910" if p == "mid_peak" else
        "#C0392B"
        for p in periods
    ]
    fig = go.Figure(go.Bar(
        x=hours,
        y=rate_values,
        text=texts,
        textposition="outside",
        marker_color=current_colors,
        marker_line_color=["#FFFFFF" if h == datetime.now().hour else "rgba(0,0,0,0)" for h in hours],
        marker_line_width=[2.5 if h == datetime.now().hour else 0 for h in hours],
        hovertext=[
            f"{_PERIOD_LABEL.get(p, p)}<br>R$ {t:.4f}/kWh"
            for p, t in zip(periods, rate_values, strict=True)
        ],
        hoverinfo="text",
    ))

    now_h = datetime.now().hour
    fig.add_annotation(
        x=now_h, y=rate_values[now_h], text=f"Now ({now_h}h)", showarrow=True,
        arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#FFFFFF",
        ax=0, ay=-35, font=dict(size=11, color="#FFFFFF"), bgcolor="#2C3E50"
    )

    adicional_txt = f" (+R$ {adicional:.4f}/kWh surcharge)" if adicional > 0 else ""
    fig.update_layout(
        title=f"Enel SP Energy Rates — Flag {bandeira}{adicional_txt}",
        xaxis=dict(title="Hour", tickmode="linear", dtick=1),
        yaxis=dict(title="R$/kWh", range=[0, max(rate_values) * 1.30]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=340,
        margin=dict(l=10, r=20, t=60, b=40),
        showlegend=False,
    )
    return fig


# ── Chart 4: Home office cost (B3, H1) ───────────────────────────────

def chart_home_office_report(db_path: str, days: int = 30) -> tuple[go.Figure, dict]:
    """
    Bar chart with explicit text labels (B3 fix).
    Y-axis range calibrated to data (H1 fix).
    Returns (figure, summary_dict).
    """
    df = _load_usage(db_path, days)
    if df.empty:
        return go.Figure(), {}

    df_office = df[df["is_office"]]
    agg = (
        df_office.groupby("device_name", as_index=False)
                 .agg(kwh=("kwh", "sum"), cost_brl=("cost_brl", "sum"))
    )
    agg["display_name"] = agg["device_name"].map(_friendly_device_name)

    total_brl   = agg["cost_brl"].sum()
    monthly_brl = total_brl / (days / 30)
    annual_brl  = monthly_brl * 12

    # B3 fix: explicit text column, not text_auto
    agg["label"] = agg["cost_brl"].apply(lambda v: f"R$ {v:.2f}")
    max_val = agg["cost_brl"].max() if not agg.empty else 1.0

    fig = px.bar(
        agg, x="display_name", y="cost_brl",
        color="device_name",
        color_discrete_sequence=["#3498DB", "#9B59B6", "#E67E22"],
        labels={"display_name": "", "cost_brl": "Cost (R$)"},
        title=f"Home Office Cost — last {days} days",
        text="label",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=340,
        margin=dict(l=10, r=20, t=60, b=40),
        yaxis=dict(title="R$", range=[0, max_val * 1.30]),  # H1 fix
    )

    summary = {
        "period_days": days,
        "total_brl":   round(total_brl, 2),
        "monthly_brl": round(monthly_brl, 2),
        "annual_brl":  round(annual_brl, 2),
        "total_kwh":   round(agg["kwh"].sum(), 1),
    }
    return fig, summary


# ── Insight of the day (U3) ───────────────────────────────────────────

def render_daily_insight(db_path: str) -> None:
    """
    Actionable insight card combining current energy rate, current weather,
    and solar irradiance. Weather data from Open-Meteo (falls back to synthetic).
    """
    pricing = generate_time_of_use_prices()
    now_h = datetime.now().hour
    rates = {r["hour"]: r for r in pricing["hourly_rates"]}
    current = rates[now_h]
    period = current["period"]
    rate = current["rate"]

    upcoming = [(h % 24, rates[h % 24]) for h in range(now_h + 1, now_h + 13)]
    cheapest = min(upcoming, key=lambda x: x[1]["rate"])

    weather = _load_weather()
    hourly_wx = {h["hour"]: h for h in weather.get("hourly", [])}
    current_wx = hourly_wx.get(now_h, {})
    irradiance = current_wx.get("solar_irradiance", 0.0)
    temperature = current_wx.get("temperature_c")
    weather_source = weather.get("data_source", "synthetic")

    solar_active = irradiance > 100.0
    solar_strong = irradiance > 500.0

    period_label = _PERIOD_LABEL.get(period, period)
    period_icon = "🟢" if period == "off_peak" else "🟡" if period == "mid_peak" else "🔴"

    weather_badge = "🌐 Open-Meteo" if weather_source == "open_meteo" else "⚙️ estimated"
    pricing_badge = pricing.get("data_source", "embedded_fallback").replace("_", " ")
    temp_str = f" · {temperature:.0f}°C" if temperature is not None else ""
    irr_str = f" · {irradiance:.0f} W/m²" if solar_active else ""

    lines = [
        f"**{period_icon} Now ({now_h}h): {period_label} — R$ {rate:.4f}/kWh**  "
        f"_(rate source: {pricing_badge} · weather: {weather_badge}{temp_str}{irr_str})_",
        "",
    ]

    if period == "peak":
        lines.append("⚠️ **Peak hour** — avoid EV charger, washing machine, and dishwasher.")
        lines.append(f"💡 Next cheap window: **{cheapest[0]}h** at R$ {cheapest[1]['rate']:.4f}/kWh")
        if solar_active:
            lines.append(f"☀️ Solar still generating ({irradiance:.0f} W/m²) — home office is partially offset.")
    elif period == "off_peak":
        lines.append("✅ **Best time to charge the EV** and run heavy appliances (lowest rate).")
        if solar_active:
            lines.append(f"🌤️ Some irradiance now ({irradiance:.0f} W/m²) — but off-peak rate beats waiting for solar.")
        else:
            lines.append("☀️ No solar generation now — all savings come from the off-peak rate.")
    else:  # mid_peak
        if solar_strong:
            lines.append(f"☀️ **Strong solar generation** ({irradiance:.0f} W/m²) — home office likely running on free solar.")
            lines.append("⚡ Delay EV charging until after 20h off-peak (R$ 0.538/kWh).")
        elif solar_active:
            lines.append(f"🌤️ Moderate solar ({irradiance:.0f} W/m²) — partially offsetting home office load.")
            lines.append(f"💡 Next cheapest window: **{cheapest[0]}h** at R$ {cheapest[1]['rate']:.4f}/kWh")
        else:
            lines.append(f"💡 Next cheapest window in next 12h: **{cheapest[0]}h** at R$ {cheapest[1]['rate']:.4f}/kWh")

    st.info("\n".join(lines))


# ── Bill breakdown by controllability ────────────────────────────────

_CTRL_COLOR = {
    "Fixed (always-on)":    "#95A5A6",
    "Home Office":          "#E67E22",
    "Flexible (shiftable)": "#2ECC71",
    "EV Charging":          "#3498DB",
}

_OFF_PEAK_RATE = 0.538   # R$/kWh — cheapest window (0h–5h)


def _classify_device(row: pd.Series) -> str:
    """Classify device by controllability using the usage_pattern from the DB schema."""
    if row["is_ev"]:
        return "EV Charging"
    if row["is_office"]:
        return "Home Office"
    if row["usage_pattern"] == "always_on":
        return "Fixed (always-on)"
    return "Flexible (shiftable)"   # scheduled or presence_dependent non-office


def chart_bill_by_controllability(db_path: str, days: int = 30) -> go.Figure:
    """Horizontal bar chart: R$ cost per device, coloured by how much João can control it."""
    df = _load_usage(db_path, days)
    if df.empty:
        return go.Figure().update_layout(title="No data available")

    df = df.copy()
    df["controllability"] = df.apply(_classify_device, axis=1)

    agg = (
        df.groupby(["device_name", "controllability"], as_index=False)
          .agg(cost_brl=("cost_brl", "sum"), kwh=("kwh", "sum"))
          .sort_values("cost_brl", ascending=True)
    )
    total_cost = max(float(agg["cost_brl"].sum()), 1.0)
    max_cost = max(float(agg["cost_brl"].max()), 1.0)
    agg["share"] = agg["cost_brl"] / total_cost
    agg["label"] = agg.apply(
        lambda row: f"R$ {row['cost_brl']:,.2f} · {row['share']:.0%}",
        axis=1,
    )

    fig = px.bar(
        agg,
        x="cost_brl",
        y="device_name",
        orientation="h",
        color="controllability",
        color_discrete_map=_CTRL_COLOR,
        text="label",
        hover_data={"kwh": ":.1f", "cost_brl": ":.2f", "share": ":.1%"},
        labels={
            "cost_brl":       "Cost (R$)",
            "device_name":    "",
            "controllability": "Category",
            "kwh":            "Consumption (kWh)",
            "share":          "Share of bill",
        },
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis=dict(range=[0, max_cost * 1.18], title="Cost (R$)", gridcolor="rgba(148,163,184,0.18)"),
        yaxis=dict(title="", automargin=True),
        legend=dict(
            title="",
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="left",
            x=0,
            itemwidth=30,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=max(420, 120 + len(agg) * 34),
        margin=dict(l=24, r=150, t=18, b=96),
        uniformtext=dict(minsize=11, mode="show"),
    )
    return fig


def render_bill_analysis(db_path: str, days: int = 30) -> None:
    """Render bill breakdown chart + actionable savings summary for João."""
    df = _load_usage(db_path, days)
    if df.empty:
        return

    df = df.copy()
    df["controllability"] = df.apply(_classify_device, axis=1)

    by_ctrl = df.groupby("controllability")["cost_brl"].sum()
    fixed      = by_ctrl.get("Fixed (always-on)", 0.0)
    office     = by_ctrl.get("Home Office", 0.0)
    shiftable  = by_ctrl.get("Flexible (shiftable)", 0.0)
    ev         = by_ctrl.get("EV Charging", 0.0)

    # Savings potential: shiftable devices shifted to off-peak
    shiftable_kwh = df[df["controllability"] == "Flexible (shiftable)"]["kwh"].sum()
    # Average current rate for shiftable devices (~mid-peak mix)
    shiftable_avg_rate = (shiftable / shiftable_kwh) if shiftable_kwh > 0 else 0.656
    shift_savings = max(0.0, shiftable_kwh * (shiftable_avg_rate - _OFF_PEAK_RATE))

    # EV savings: if currently charging at mixed rates, shift to off-peak
    ev_kwh = df[df["controllability"] == "EV Charging"]["kwh"].sum()
    ev_avg_rate = (ev / ev_kwh) if ev_kwh > 0 else 0.656
    ev_savings = max(0.0, ev_kwh * (ev_avg_rate - _OFF_PEAK_RATE))

    by_device = (
        df.groupby(["device_name", "controllability"], as_index=False)
          .agg(cost_brl=("cost_brl", "sum"), kwh=("kwh", "sum"))
          .sort_values("cost_brl", ascending=False)
    )
    total_cost = max(float(by_device["cost_brl"].sum()), 1.0)

    st.caption(f"Cost distribution by device for the selected {days}-day period.")
    top_cols = st.columns(3)
    for col, (_, row) in zip(top_cols, by_device.head(3).iterrows(), strict=False):
        share = row["cost_brl"] / total_cost
        col.metric(
            row["device_name"],
            f"R$ {row['cost_brl']:,.2f}",
            delta=f"{share:.0%} of bill",
            help=f"{row['controllability']} · {row['kwh']:.1f} kWh",
        )

    st.plotly_chart(
        chart_bill_by_controllability(db_path, days),
        width="stretch",
    )

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔒 Fixed costs",      f"R$ {fixed:,.2f}",     help="Always-on: fridge, router — baseline, can't reduce")
    c2.metric("🖥️ Home Office",      f"R$ {office:,.2f}",    help="PC + Monitor + AC escritório — reduce or claim subsidy from employer")
    c3.metric("🔄 Flexible load",    f"R$ {shiftable:,.2f}", help="Washing machine, shower, lights — shift to off-peak 0h–5h")
    c4.metric("🚗 EV Charging",      f"R$ {ev:,.2f}",        help="Tesla Model 3 — save by charging 0h–5h at R$ 0.538/kWh")

    # Actionable savings callout
    total_savings = shift_savings + ev_savings
    if total_savings > 1.0:
        monthly_factor = 30 / max(days, 1)
        monthly_savings = total_savings * monthly_factor
        st.success(
            f"**💡 Savings opportunity this period: R\\$ {total_savings:,.2f}**  "
            f"(≈ R\\$ {monthly_savings:,.2f}/month) — shift flexible devices and EV charging "
            f"to the off-peak window (0h–5h, R\\$ {_OFF_PEAK_RATE}/kWh)."
        )


# ── Layer 1: ML Usage Forecast ───────────────────────────────────────

_FORECAST_CATEGORIES = [
    ("ev",        "EV (Tesla)",    "#E74C3C"),
    ("hvac",      "HVAC",          "#F39C12"),
    ("appliance", "Appliances",    "#2ECC71"),
    ("computer",  "Home Office",   "#3498DB"),
]

_METHOD_LABEL = {
    "sklearn_hgb":    "🤖 sklearn · HistGradientBoosting",
    "seasonal_naive": "📊 Seasonal Naive (baseline)",
}


def render_ml_forecast_section(db_path: str) -> None:
    """Layer 1: 24h consumption forecast with validation-aware messaging."""
    params24 = UsageForecastParams(horizon_hours=24)
    hours = list(range(24))

    total_result = route_usage_forecast(db_path=db_path, device_type=None, params=params24)
    method = total_result.get("method", "seasonal_naive")
    method_label = _METHOD_LABEL.get(method, method)
    validation = total_result.get("validation")
    total_pts = {
        int(p["timestamp"][11:13]): p["predicted_kwh"]
        for p in total_result.get("points", [])
    }

    db = DatabaseManager(db_path=db_path)
    series = load_hourly_usage_series(db, device_type=None)
    baseline_pts_raw = seasonal_naive_usage_forecast(series, params24)
    baseline_pts = {int(p["timestamp"][11:13]): p["predicted_kwh"] for p in baseline_pts_raw}

    cat_totals: dict[str, float] = {}
    for device_type, label, _ in _FORECAST_CATEGORIES:
        routed = route_usage_forecast(db_path=db_path, device_type=device_type, params=params24)
        cat_totals[label] = routed.get("total_predicted_kwh", 0.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours,
        y=[baseline_pts.get(h, 0.0) for h in hours],
        name="Baseline (seasonal naive)",
        mode="lines",
        line=dict(color="#95A5A6", width=1.5, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=hours,
        y=[total_pts.get(h, 0.0) for h in hours],
        name=method_label,
        mode="lines+markers",
        line=dict(color="#3498DB", width=2.5),
        marker=dict(size=5),
        fill="tozeroy",
        fillcolor="rgba(52,152,219,0.10)",
    ))

    now_h = datetime.now().hour
    fig.add_vline(
        x=now_h,
        line_width=1.5,
        line_dash="dot",
        line_color="#95A5A6",
        annotation_text=f"Now ({now_h}h)",
        annotation_position="top right",
        annotation_font_size=11,
    )
    fig.update_layout(
        title=f"24h Consumption Forecast — Total [{method_label}]",
        xaxis_title="Hour of day",
        yaxis_title="kWh",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=70, b=40),
        xaxis=dict(dtick=2, range=[0, 23], gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", rangemode="nonnegative"),
    )

    total_24h = total_result.get("total_predicted_kwh", 0.0)
    peak_h = max(total_pts, key=lambda h: total_pts[h]) if total_pts else 12
    peak_kwh = total_pts.get(peak_h, 0.0)

    metrics = st.columns(4)
    metrics[0].metric("Total (next 24h)", f"{total_24h:.2f} kWh")
    metrics[1].metric("Peak Hour", f"{peak_h}h ({peak_kwh:.2f} kWh)")
    metrics[2].metric("Forecast Method", method_label.replace("🤖 ", "").replace("📊 ", ""))
    validation_label = "Available" if validation else "Missing"
    metrics[3].metric("Hold-out Metrics", validation_label)
    st.plotly_chart(fig, width="stretch")

    if validation:
        rmse_delta = validation["rmse_improvement_pct"]
        mae_delta = validation["mae_improvement_pct"]
        vcols = st.columns(4)
        vcols[0].metric("Model RMSE", f"{validation['model_rmse']:.4f}")
        vcols[1].metric("Baseline RMSE", f"{validation['baseline_rmse']:.4f}")
        vcols[2].metric("RMSE vs baseline", f"{rmse_delta:+.2f}%")
        vcols[3].metric("MAE vs baseline", f"{mae_delta:+.2f}%")
        if rmse_delta >= 0 and mae_delta >= 0:
            st.caption("Validation says the ML model improved on the baseline in this hold-out window.")
        else:
            st.caption("Validation is mixed: the seasonal baseline still wins on part of the hold-out. Keep both visible.")
    else:
        st.caption("Model artifact has no saved hold-out metrics yet. Re-run local training to publish validation.")

    with st.expander("Category breakdown", expanded=False):
        st.caption("Independent device-family forecasts. They are useful for ranking likely load drivers, but they do not need to sum exactly to the household total model.")
        cols = st.columns(len(_FORECAST_CATEGORIES))
        category_total = sum(cat_totals.values())
        for i, (_, label, _) in enumerate(_FORECAST_CATEGORIES):
            kwh = cat_totals.get(label, 0.0)
            pct = (kwh / category_total * 100) if category_total > 0 else 0.0
            cols[i].metric(label, f"{kwh:.2f} kWh", f"{pct:.0f}% of category view")


# ── Layer 2: Optimization Recommendations ────────────────────────────

_CONFIDENCE_COLOR = {"high": "🟢", "medium": "🟡", "low": "🔴"}
_CONFIDENCE_HELP  = {
    "high":   "ML model trained on this device type with sufficient data",
    "medium": "ML model available but savings are small — treat as indicative",
    "low":    "Seasonal naive baseline — train ML model to improve confidence",
}


def render_recommendations(db_path: str, horizon_days: int = 30) -> None:
    """Layer 2: Ranked savings recommendations from the optimizer.

    Shows what João can change, how much he saves, and how confident
    the estimate is (sklearn_hgb = high / seasonal_naive = low).
    """
    from energy_advisor.services.optimizer import generate_recommendations

    with st.spinner("Generating recommendations…"):
        recs = generate_recommendations(db_path=db_path, horizon_days=horizon_days)

    if not recs:
        st.info("No optimization opportunities found for the selected period.")
        return

    total_30d = sum(r.savings_30d_brl for r in recs)
    total_90d = sum(r.savings_90d_brl for r in recs)

    # ── Header metrics ────────────────────────────────────────────────
    h1, h2, h3 = st.columns(3)
    h1.metric(
        "💰 Total Savings Potential (30d)",
        f"R$ {total_30d:,.2f}",
        help="Sum of all recommendations projected to 30 days",
    )
    h2.metric(
        "📅 Projected (90d / 3 months)",
        f"R$ {total_90d:,.2f}",
        help="Maximum horizon: 90 days (3 months of historical data used)",
    )
    h3.metric(
        "🔍 Recommendations",
        f"{len(recs)} opportunities",
        help="Based on 7-day ML forecast × TOU load shifting",
    )

    st.markdown("---")

    # ── Recommendation cards ──────────────────────────────────────────
    for rec in recs:
        conf_icon  = _CONFIDENCE_COLOR.get(rec.confidence, "⚪")
        method_tag = "🤖 ML" if rec.method == "sklearn_hgb" else "📊 Baseline"
        conf_help  = _CONFIDENCE_HELP.get(rec.confidence, "")

        with st.container(border=True):
            col_info, col_nums = st.columns([3, 1])

            with col_info:
                st.markdown(
                    f"**#{rec.rank} — {rec.label}**  "
                    f"{conf_icon} {rec.confidence.capitalize()} confidence · {method_tag}"
                )
                st.markdown(f"📌 **Action:** {rec.action}")
                st.caption(
                    f"Current pattern: {rec.current_window}  →  "
                    f"Optimal: {rec.optimal_window}"
                )
                if rec.peak_kwh_predicted > 0:
                    st.caption(
                        f"Predicted in peak hours (18h–20h): **{rec.peak_kwh_predicted:.1f} kWh/week** · "
                        f"mid-peak: **{rec.mid_kwh_predicted:.1f} kWh/week**"
                    )

            with col_nums:
                st.metric("30-day savings",  f"R$ {rec.savings_30d_brl:,.2f}")
                st.metric("90-day savings",  f"R$ {rec.savings_90d_brl:,.2f}")
                st.caption(conf_help)

    # ── Methodology note ──────────────────────────────────────────────
    st.caption(
        "**Methodology:** 7-day hourly forecast (ML or baseline) × "
        "shiftable fraction per device × (TOU current rate − off-peak rate R$ 0.538/kWh). "
        "Projected linearly to 30/90 days. "
        "Actual savings depend on João's behavior change."
    )


# ── Solar Forecast Today ──────────────────────────────────────────────

def render_solar_forecast_today(db_path: str) -> None:
    """Full-width section: Open-Meteo irradiance → predicted solar kWh today,
    overlaid with today's recorded generation from the DB.

    Data sources are labelled explicitly so the API integration is visible
    in the UI — not just in the logs.
    """
    weather = _load_weather()
    data_source = weather.get("data_source", "synthetic")
    hourly_wx = {h["hour"]: h for h in weather.get("hourly", [])}

    # Open-Meteo irradiance → predicted kWh per hour for the full day
    all_hours = list(range(24))
    forecast_kwh = [
        round(
            (hourly_wx.get(h, {}).get("solar_irradiance", 0.0) / 1000.0)
            * _PANEL_KWP * _PANEL_EFF,
            3,
        )
        for h in all_hours
    ]

    # Today's recorded solar from DB (synthetic in demo mode)
    df_solar = _load_solar(db_path, days=1)
    today = datetime.now().date()
    actual_by_hour: dict[int, float] = {}
    if not df_solar.empty:
        df_today = df_solar[df_solar["timestamp"].dt.date == today]
        actual_by_hour = df_today.groupby("hour")["kwh"].sum().to_dict()

    # ── Figure ────────────────────────────────────────────────────────
    fig = go.Figure()

    source_name = "Open-Meteo" if data_source == "open_meteo" else "Estimated (API unavailable)"
    source_icon = "🌐" if data_source == "open_meteo" else "⚙️"

    fig.add_trace(go.Scatter(
        x=all_hours,
        y=forecast_kwh,
        name=f"Forecast · {source_name}",
        mode="lines",
        line=dict(color="#F39C12", width=2.5, dash="dash"),
        fill="tozeroy",
        fillcolor="rgba(243,156,18,0.10)",
    ))

    if actual_by_hour:
        sorted_hours = sorted(actual_by_hour)
        fig.add_trace(go.Scatter(
            x=sorted_hours,
            y=[actual_by_hour[h] for h in sorted_hours],
            name="Recorded · DB (simulated)",
            mode="lines+markers",
            line=dict(color="#27AE60", width=2),
            marker=dict(size=5),
        ))

    now_h = datetime.now().hour
    fig.add_vline(
        x=now_h,
        line_width=1.5, line_dash="dot", line_color="#95A5A6",
        annotation_text=f"Now ({now_h}h)",
        annotation_position="top right",
        annotation_font_size=11,
    )

    fig.update_layout(
        title=(
            f"Solar Forecast — Today   "
            f"{source_icon} {source_name} · 4kWp · η = 85%"
        ),
        xaxis_title="Hour of day",
        yaxis_title="kWh",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=70, b=40),
        xaxis=dict(dtick=2, range=[0, 23], gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", rangemode="nonnegative"),
    )

    # ── Summary metrics ───────────────────────────────────────────────
    total_forecast = sum(forecast_kwh)
    peak_h = forecast_kwh.index(max(forecast_kwh)) if any(v > 0 for v in forecast_kwh) else 12
    current_irr = hourly_wx.get(now_h, {}).get("solar_irradiance", 0.0)
    current_temp = hourly_wx.get(now_h, {}).get("temperature_c")
    total_actual = sum(actual_by_hour.values()) if actual_by_hour else None

    m1, m2, m3, m4 = st.columns(4, gap="medium")
    m1.metric(
        "Forecast", f"{total_forecast:.1f} kWh",
        help="Irradiance → kWh = W/m² ÷ 1000 × 4kWp × 0.85",
    )
    m2.metric(
        "Peak", f"{peak_h}h",
        help="Hour with highest predicted irradiance",
    )
    temp_label = f"{current_temp:.1f}°C · " if current_temp is not None else ""
    m3.metric(
        "Irradiance", f"{current_irr:.0f} W/m²",
        help=f"{temp_label}{source_name}",
    )
    if total_actual is not None:
        m4.metric(
            "Recorded", f"{total_actual:.1f} kWh",
            help="Accumulated kWh from DB today (synthetic in demo mode)",
        )
    else:
        m4.metric("Recorded", "—")

    st.plotly_chart(fig, width="stretch")

    # Provenance note — makes the API integration explicit to any reader
    note = (
        f"{source_icon} **Forecast:** {source_name} — irradiance (W/m²) → kWh via "
        f"`W/m² ÷ 1000 × {_PANEL_KWP}kWp × {_PANEL_EFF}`"
    )
    if actual_by_hour:
        note += (
            "  ·  🗄️ **Recorded:** synthetic data (demo mode — "
            "replace with inverter monitoring API in production)"
        )
    st.caption(note)
