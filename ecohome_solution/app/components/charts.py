"""
Visualization components for the EcoHome Energy Advisor dashboard.
All public functions return Plotly figures ready for st.plotly_chart().
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from energy_advisor.services.database import DatabaseManager
from energy_advisor.services.pricing import generate_time_of_use_prices
from energy_advisor.services.forecasting import generate_hourly_forecast

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

_AVG_TARIFF_BRL = 0.656   # Enel SP mid-peak base rate used for solar savings estimate


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
    """5-card KPI row. Home office cost uses HOME_OFFICE_DEVICES (fixes B1)."""
    df_usage = _load_usage(db_path, days)
    df_solar = _load_solar(db_path, days)

    total_kwh  = df_usage["kwh"].sum()      if not df_usage.empty else 0.0
    total_brl  = df_usage["cost_brl"].sum() if not df_usage.empty else 0.0
    solar_kwh  = df_solar["kwh"].sum()      if not df_solar.empty else 0.0

    # B1 fix: filter by device name, not by location
    office_brl = (
        df_usage[df_usage["is_office"]]["cost_brl"].sum()
        if not df_usage.empty else 0.0
    )

    # K1: solar self-sufficiency
    self_suff = (solar_kwh / total_kwh * 100) if total_kwh > 0 else 0.0

    # K2/K3: solar savings and net grid cost
    solar_savings = solar_kwh * _AVG_TARIFF_BRL
    net_cost = max(0.0, total_brl - solar_savings)

    row1 = st.columns(5)
    row1[0].metric("⚡ Consumption",        f"{total_kwh:,.0f} kWh",      help=f"Last {days} days")
    row1[1].metric("💸 Gross Cost",         f"R$ {total_brl:,.2f}",       help="Before solar offset")
    row1[2].metric("☀️ Solar Generation",   f"{solar_kwh:,.0f} kWh",      help=f"4kWp panel — {days} days")
    row1[3].metric("🔋 Self-sufficiency",   f"{self_suff:.0f}%",          help="Solar ÷ Total consumption")
    row1[4].metric("🖥️ Home Office Cost",   f"R$ {office_brl:,.2f}",      help="PC + Monitor + AC office · from start of day, 30 days ago")

    row2 = st.columns(3)
    row2[0].metric("☀️ Solar Savings",      f"R$ {solar_savings:,.2f}",   help=f"Solar × R$ {_AVG_TARIFF_BRL}/kWh")
    row2[1].metric("🔌 Net Grid Cost",      f"R$ {net_cost:,.2f}",        help="Gross cost − solar savings")
    row2[2].metric("📅 Period",             f"{days} days",               help="Adjust with the sidebar slider")


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
    agg["pct"]           = (agg["kwh"] / total_kwh * 100).round(1)
    agg["label"]         = agg.apply(lambda r: f"{r['pct']:.0f}%", axis=1)

    fig = px.bar(
        agg, x="kwh", y="device_name", orientation="h",
        color="pattern_label",
        color_discrete_map={v: _PATTERN_COLOR[k] for k, v in _PATTERN_LABEL.items()},
        text="label",
        hover_data={"cost_brl": ":.2f", "kwh": ":.1f", "pct": ":.1f"},
        labels={
            "kwh":           "Consumption (kWh)",
            "device_name":   "",
            "pattern_label": "Category",
            "cost_brl":      "Cost (R$)",
            "pct":           "% of total",
        },
        title=f"Consumption by Device — last {days} days (EV shown separately)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=10, r=60, t=60, b=20),
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
        f"Average R$ {avg_cost:.2f} per charging day · "
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

    # S2: surplus area — where solar > consumption
    surplus_y = [max(0.0, s - u) for s, u in zip(solar_vals, usage_vals)]
    surplus_base = [min(s, u) for s, u in zip(solar_vals, usage_vals)]
    fig.add_trace(go.Scatter(
        x=hours + hours[::-1],
        y=[b + s for b, s in zip(surplus_base, surplus_y)] + surplus_base[::-1],
        fill="toself",
        fillcolor="rgba(39,174,96,0.25)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Solar Surplus → Grid",
        hoverinfo="skip",
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
        title=f"Solar vs Consumption — hourly average ({days} days)",
        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
        yaxis=dict(title="kW (avg)"),   # S1 fix
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(l=10, r=20, t=60, b=40),
    )
    return fig


# ── Chart 3: TOU tariff rates (T1, T2) ───────────────────────────────

def chart_tou_rates(date: str | None = None) -> go.Figure:
    """
    Bar chart of hourly tariffs.
    Shows label only on first bar of each period (T1).
    Adds vertical 'Now' line (T2).
    """
    pricing   = generate_time_of_use_prices(date)
    rates     = pricing["hourly_rates"]
    bandeira  = pricing["bandeira"].replace("_", " ").title()
    adicional = pricing["bandeira_adicional_brl"]

    hours   = [r["hour"]   for r in rates]
    tariffs = [r["rate"]   for r in rates]
    periods = [r["period"] for r in rates]

    # T1: label only on first bar of each period group
    texts, seen = [], set()
    for p, t in zip(periods, tariffs):
        if p not in seen:
            texts.append(f"R${t:.3f}")
            seen.add(p)
        else:
            texts.append("")

    fig = go.Figure(go.Bar(
        x=hours,
        y=tariffs,
        text=texts,
        textposition="outside",
        marker_color=[
            "#27AE60" if p == "off_peak" else
            "#F39C12" if p == "mid_peak" else
            "#E74C3C"
            for p in periods
        ],
        hovertext=[
            f"{_PERIOD_LABEL.get(p, p)}<br>R$ {t:.4f}/kWh"
            for p, t in zip(periods, tariffs)
        ],
        hoverinfo="text",
    ))

    # T2: current hour marker
    now_h = datetime.now().hour
    fig.add_vline(
        x=now_h, line_width=2, line_dash="dash", line_color="#2C3E50",
        annotation_text=f"Now ({now_h}h)",
        annotation_position="top right",
        annotation_font_size=11,
    )

    adicional_txt = f" (+R$ {adicional:.4f}/kWh surcharge)" if adicional > 0 else ""
    fig.update_layout(
        title=f"Enel SP Tariffs — Bandeira {bandeira}{adicional_txt}",
        xaxis=dict(title="Hour", tickmode="linear", dtick=1),
        yaxis=dict(title="R$/kWh", range=[0, max(tariffs) * 1.30]),
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

    total_brl   = agg["cost_brl"].sum()
    monthly_brl = total_brl / (days / 30)
    annual_brl  = monthly_brl * 12

    # B3 fix: explicit text column, not text_auto
    agg["label"] = agg["cost_brl"].apply(lambda v: f"R$ {v:.2f}")
    max_val = agg["cost_brl"].max() if not agg.empty else 1.0

    fig = px.bar(
        agg, x="device_name", y="cost_brl",
        color="device_name",
        color_discrete_sequence=["#3498DB", "#9B59B6", "#E67E22"],
        labels={"device_name": "", "cost_brl": "Cost (R$)"},
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
    Actionable insight card combining real-time tariff, current weather,
    and solar irradiance. Weather data from Open-Meteo (falls back to synthetic).
    """
    pricing = generate_time_of_use_prices()
    now_h   = datetime.now().hour
    rates   = {r["hour"]: r for r in pricing["hourly_rates"]}
    current = rates[now_h]
    period  = current["period"]
    rate    = current["rate"]

    # Find cheapest window in the next 12 hours
    upcoming = [(h % 24, rates[h % 24]) for h in range(now_h + 1, now_h + 13)]
    cheapest = min(upcoming, key=lambda x: x[1]["rate"])

    # Real-time weather
    weather      = _load_weather()
    hourly_wx    = {h["hour"]: h for h in weather.get("hourly", [])}
    current_wx   = hourly_wx.get(now_h, {})
    irradiance   = current_wx.get("solar_irradiance", 0.0)
    temperature  = current_wx.get("temperature_c")
    condition    = current_wx.get("condition", "")
    data_source  = weather.get("data_source", "synthetic")

    # Irradiance thresholds for a 4kWp panel (roughly: >500 = good generation)
    solar_active = irradiance > 100.0
    solar_strong = irradiance > 500.0

    period_label = _PERIOD_LABEL.get(period, period)
    period_icon  = "🟢" if period == "off_peak" else "🟡" if period == "mid_peak" else "🔴"

    source_badge = "🌐 Open-Meteo" if data_source == "open_meteo" else "⚙️ estimated"
    temp_str     = f" · {temperature:.0f}°C" if temperature is not None else ""
    irr_str      = f" · {irradiance:.0f} W/m²" if solar_active else ""

    lines = [
        f"**{period_icon} Now ({now_h}h): {period_label} — R$ {rate:.4f}/kWh**  "
        f"_({source_badge}{temp_str}{irr_str})_",
        "",
    ]

    if period == "peak":
        lines.append("⚠️ **Peak hour** — avoid EV charger, washing machine, and dishwasher.")
        lines.append(f"💡 Next cheap window: **{cheapest[0]}h** at R$ {cheapest[1]['rate']:.4f}/kWh")
        if solar_active:
            lines.append(f"☀️ Solar still generating ({irradiance:.0f} W/m²) — home office is partially offset.")
    elif period == "off_peak":
        lines.append("✅ **Best time to charge the EV** and run heavy appliances (lowest tariff).")
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
    agg["label"] = agg["cost_brl"].apply(lambda v: f"R$ {v:,.2f}")

    fig = px.bar(
        agg, x="cost_brl", y="device_name", orientation="h",
        color="controllability",
        color_discrete_map=_CTRL_COLOR,
        text="label",
        hover_data={"kwh": ":.1f", "cost_brl": ":.2f"},
        labels={
            "cost_brl":       "Cost (R$)",
            "device_name":    "",
            "controllability": "Category",
            "kwh":            "Consumption (kWh)",
        },
        title=f"Where Your Money Goes — last {days} days",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=10, r=80, t=60, b=20),
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
    total      = fixed + office + shiftable + ev

    # Savings potential: shiftable devices shifted to off-peak
    shiftable_kwh = df[df["controllability"] == "Flexible (shiftable)"]["kwh"].sum()
    # Average current rate for shiftable devices (~mid-peak mix)
    shiftable_avg_rate = (shiftable / shiftable_kwh) if shiftable_kwh > 0 else 0.656
    shift_savings = max(0.0, shiftable_kwh * (shiftable_avg_rate - _OFF_PEAK_RATE))

    # EV savings: if currently charging at mixed rates, shift to off-peak
    ev_kwh = df[df["controllability"] == "EV Charging"]["kwh"].sum()
    ev_avg_rate = (ev / ev_kwh) if ev_kwh > 0 else 0.656
    ev_savings = max(0.0, ev_kwh * (ev_avg_rate - _OFF_PEAK_RATE))

    st.plotly_chart(
        chart_bill_by_controllability(db_path, days),
        use_container_width=True,
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
