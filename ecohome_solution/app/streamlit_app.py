"""
EcoHome Energy Advisor — Streamlit interface.

Run from ecohome_solution/:
    uv run streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Ensure energy_advisor package is importable from any working directory
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

st.set_page_config(
    page_title="EcoHome Energy Advisor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from energy_advisor.config import Settings
from energy_advisor.services.pricing import get_bandeira
from app.components.charts import (
    chart_consumption_by_device,
    chart_home_office_report,
    chart_solar_vs_consumption,
    chart_tou_rates,
    render_metrics,
)
from app.components.chat import render_chat

settings = Settings()

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

    bandeira_nome, adicional = get_bandeira(datetime.now())
    _bandeira_icon = {
        "verde": "🟢", "amarela": "🟡",
        "vermelha_1": "🔴", "vermelha_2": "🔴",
    }
    icon = _bandeira_icon.get(bandeira_nome, "⚪")
    st.markdown(f"**{icon} ANEEL Tariff Flag**")
    st.markdown(f"**{bandeira_nome.replace('_', ' ').title()}**")
    st.caption(
        f"+R$ {adicional:.4f}/kWh surcharge" if adicional > 0
        else "No surcharge on base tariff"
    )
    st.divider()

    days_filter = st.slider("Analysis period (days)", 7, 90, 30, step=7)
    st.divider()
    st.caption("v0.2.0 · feat/portfolio-refactor")

# ── Main tabs ─────────────────────────────────────────────────────────
tab_dash, tab_chat = st.tabs(["📊 Dashboard", "💬 Ask the Advisor"])

# ── Dashboard tab ─────────────────────────────────────────────────────
with tab_dash:
    st.header("Energy Dashboard — João")
    st.caption(f"Distributor: Enel SP · Last {days_filter} days")

    render_metrics(settings.db_path, days=days_filter)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            chart_consumption_by_device(settings.db_path, days=days_filter),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            chart_solar_vs_consumption(settings.db_path, days=days_filter),
            use_container_width=True,
        )

    st.divider()

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(chart_tou_rates(), use_container_width=True)
        st.caption(
            "🟢 Off-peak night (0h–5h): best window for EV charging and heavy appliances.  "
            "🔴 Peak (18h–20h): avoid intensive consumption."
        )
    with col4:
        fig_office, summary = chart_home_office_report(settings.db_path, days=days_filter)
        st.plotly_chart(fig_office, use_container_width=True)
        if summary:
            st.info(
                f"💼 **Home Office Cost Report**\n\n"
                f"Period total: **R$ {summary['total_brl']:.2f}** "
                f"({summary['total_kwh']:.1f} kWh)\n\n"
                f"Monthly projection: **R$ {summary['monthly_brl']:.2f}**  \n"
                f"Annual projection: **R$ {summary['annual_brl']:.2f}**\n\n"
                "_Use this data to negotiate a home office energy subsidy with your employer._"
            )

# ── Chat tab ──────────────────────────────────────────────────────────
with tab_chat:
    st.header("Ask the Energy Advisor")
    st.caption("ReAct agent with access to consumption data, solar generation, tariffs, and knowledge base.")
    render_chat()
