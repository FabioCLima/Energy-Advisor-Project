"""
EcoHome Energy Advisor — Streamlit interface.

Run from project root:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.components.charts import (
    chart_consumption_by_device,
    chart_home_office_report,
    chart_solar_vs_consumption,
    build_dashboard_export_csv,
    chart_tou_rates,
    render_bill_analysis,
    render_daily_insight,
    render_ev_summary,
    render_metrics,
    render_ml_forecast_section,
    render_recommendations,
    render_solar_forecast_today,
    render_top_consumers,
)
from app.components.chat import render_chat
from energy_advisor.bootstrap.runtime import ensure_demo_assets
from energy_advisor.config import Settings
from energy_advisor.services.pricing import generate_time_of_use_prices

st.set_page_config(
    page_title="EcoHome Energy Advisor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = Settings()


@st.cache_resource(show_spinner="Preparing demo data and local models…")
def _prepare_runtime() -> None:
    ensure_demo_assets(settings=settings, ensure_vectorstore_index=False)


_prepare_runtime()

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚡ EcoHome")
    st.caption("AI Energy Advisor")
    st.divider()

    st.markdown("**👤 Profile**")
    st.markdown("João · Python Developer")
    st.markdown("📍 São Paulo, SP")
    st.markdown("🏢 Home office Mon–Fri")
    st.markdown("🚗 Tesla Model 3")
    st.markdown("☀️ 4kWp solar panel")
    st.divider()

    pricing_now = generate_time_of_use_prices(datetime.now().strftime("%Y-%m-%d"))
    bandeira_nome = pricing_now["bandeira"]
    adicional = pricing_now["bandeira_adicional_brl"]
    pricing_source = pricing_now.get("data_source", "embedded_fallback").replace("_", " ")
    fetched_at = pricing_now.get("fetched_at")
    _bandeira_icon = {
        "verde": "🟢", "amarela": "🟡",
        "vermelha_1": "🔴", "vermelha_2": "🔴",
    }
    icon = _bandeira_icon.get(bandeira_nome, "⚪")
    st.markdown(f"**{icon} ANEEL Energy Rate Flag**")
    st.markdown(f"**{bandeira_nome.replace('_', ' ').title()}**")
    st.caption(
        f"+R$ {adicional:.4f}/kWh surcharge" if adicional > 0
        else "No surcharge on base rate"
    )
    if fetched_at:
        st.caption(f"Source: {pricing_source} · refreshed {fetched_at}")
    else:
        st.caption(f"Source: {pricing_source} · using bundled fallback values")
    st.divider()

    days_filter = st.slider("Analysis period (days)", 7, 90, 30, step=7)
    st.download_button(
        "Export dashboard CSV",
        data=build_dashboard_export_csv(settings.db_path, days_filter),
        file_name=f"ecohome_dashboard_{days_filter}d.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.divider()
    st.caption("v0.2.0 · feat/portfolio-refactor")

# ── Main tabs ─────────────────────────────────────────────────────────
tab_dash, tab_chat = st.tabs(["📊 Dashboard", "💬 Ask the Advisor"])

# ── Dashboard tab ─────────────────────────────────────────────────────
with tab_dash:
    st.header("Energy Dashboard — João")
    st.caption(f"Distributor: Enel SP · Analysis window: last {days_filter} days")

    render_metrics(settings.db_path, days=days_filter)
    st.divider()

    # U3: Actionable insight of the day
    render_daily_insight(settings.db_path)
    st.divider()

    # U2: Left column = device breakdown + home office
    #     Right column = time-series analysis (solar + rates)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Top Consumers")
        render_top_consumers(settings.db_path, days=days_filter)
        st.plotly_chart(
            chart_consumption_by_device(settings.db_path, days=days_filter),
            width="stretch",
        )
        st.divider()
        # D1: Tesla in its own section
        st.markdown("#### 🚗 EV Charging — Tesla Model 3")
        render_ev_summary(settings.db_path, days=days_filter)

    with col_right:
        # Solar historical chart
        st.plotly_chart(
            chart_solar_vs_consumption(settings.db_path, days=days_filter),
            width="stretch",
        )
        # Solar forecast today — continuous narrative: past → today
        st.markdown("#### ☀️ Solar Forecast — Today")
        st.caption("Real-time irradiance from Open-Meteo converted to kWh for João's 4kWp panel.")
        render_solar_forecast_today(settings.db_path)
        st.divider()
        # Rate chart
        st.plotly_chart(chart_tou_rates(), width="stretch")
        st.caption(
            "🟢 Off-peak night (0h–5h): best window for EV charging and heavy appliances.  "
            "🔴 Peak (18h–20h): avoid intensive consumption."
        )

    st.divider()

    # ── Optimization Recommendations ───────────────────────────────────
    st.markdown("#### 💡 Optimization Recommendations")
    horizon = st.select_slider(
        "Projection horizon",
        options=[7, 14, 30, 60, 90],
        value=30,
        format_func=lambda x: f"{x} days",
    )
    st.caption(
        "Ranked savings opportunities: ML forecast × TOU load shifting. "
        "Savings are quantified in R$ and projected to the selected horizon."
    )
    render_recommendations(settings.db_path, horizon_days=horizon)

    with st.expander("📈 24h Usage Forecast (methodology)"):
        st.caption(
            "Predicted consumption for the next 24h by device category. "
            "Blue line = ML model (sklearn · HistGradientBoosting). "
            "Grey dotted = seasonal naive baseline (for comparison)."
        )
        render_ml_forecast_section(settings.db_path)

    st.divider()

    # Bill breakdown by controllability — full width
    st.markdown("#### 💰 Where Your Money Goes")
    st.caption("Devices grouped by how much control João has over their cost.")
    render_bill_analysis(settings.db_path, days=days_filter)

    st.divider()

    # Home office cost report — full width section
    st.markdown("#### 💼 Home Office Cost Report")
    col_ho, col_info = st.columns([2, 1])
    with col_ho:
        fig_office, summary = chart_home_office_report(settings.db_path, days=days_filter)
        st.plotly_chart(fig_office, width="stretch")
    with col_info:
        if summary:
            st.metric("Period Total", f"R$ {summary['total_brl']:.2f}", help=f"{summary['total_kwh']:.1f} kWh")
            st.metric("Monthly Projection", f"R$ {summary['monthly_brl']:.2f}")
            st.metric("Annual Projection", f"R$ {summary['annual_brl']:.2f}")
            st.info(
                "_Use this data to negotiate a home office energy subsidy with your employer._"
            )

# ── Chat tab ──────────────────────────────────────────────────────────
with tab_chat:
    st.header("Ask the Energy Advisor")
    st.caption("ReAct agent with access to consumption data, solar generation, rates, and knowledge base.")
    render_chat()
