"""Operations tab — the agent's own telemetry, rendered for humans.

Reads the local JSONL traces through the same aggregation the CLI reader
uses (energy_advisor.observability.report), so the dashboard and the
terminal always tell the same story: cost per day, success rate, latency
percentiles, budget flags and tool usage.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from energy_advisor.config import Settings
from energy_advisor.observability.report import load_traces, summarize_traces

_TRANSPARENT = {"plot_bgcolor": "rgba(0,0,0,0)", "paper_bgcolor": "rgba(0,0,0,0)"}


def _chart_daily(by_day: dict) -> go.Figure:
    frame = pd.DataFrame(
        [{"day": day, **values} for day, values in by_day.items()]
    )
    fig = go.Figure()
    fig.add_bar(
        x=frame["day"], y=frame["requests"], name="Requests",
        marker_color="#60a5fa", yaxis="y",
    )
    fig.add_scatter(
        x=frame["day"], y=frame["cost_usd"], name="Cost (USD)",
        mode="lines+markers", line=dict(color="#f59e0b", width=2), yaxis="y2",
    )
    fig.update_layout(
        title="Requests and cost per day",
        yaxis=dict(title="Requests", gridcolor="rgba(148,163,184,0.18)"),
        yaxis2=dict(title="Cost (USD)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.12),
        height=320,
        margin=dict(t=60, b=30),
        **_TRANSPARENT,
    )
    return fig


def _chart_top_tools(top_tools: dict) -> go.Figure:
    frame = pd.DataFrame(
        {"tool": list(top_tools.keys()), "calls": list(top_tools.values())}
    ).sort_values("calls")
    fig = px.bar(frame, x="calls", y="tool", orientation="h")
    fig.update_traces(marker_color="#34d399")
    fig.update_layout(
        title="Tool usage",
        xaxis=dict(title="Calls", gridcolor="rgba(148,163,184,0.18)"),
        yaxis=dict(title=""),
        height=max(260, 36 * len(frame) + 80),
        margin=dict(t=60, b=30),
        **_TRANSPARENT,
    )
    return fig


def render_operations() -> None:
    """Render the Operations tab from local agent traces."""
    settings = Settings()
    traces = load_traces(settings.observability_trace_path)
    summary = summarize_traces(traces)

    col_title, col_refresh = st.columns([5, 1])
    with col_title:
        st.caption(
            f"Local traces from `{settings.observability_trace_path}` — every chat "
            "message and API call lands here. Same numbers as "
            "`python -m energy_advisor.observability.report`."
        )
    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    if summary.get("total_requests", 0) == 0:
        st.info(
            "No traces yet. Ask the advisor something in the **💬 Ask the Advisor** "
            "tab and come back — every request is traced."
        )
        return

    # ── Headline metrics ─────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Requests", summary["total_requests"])
    m2.metric("Success rate", f"{summary['success_rate']:.0%}")
    m3.metric("Total cost", f"${summary['total_cost_usd']:.4f}")
    m4.metric("Avg latency", f"{summary['avg_latency_s']:.1f}s")
    m5.metric("p95 latency", f"{summary['p95_latency_s']:.1f}s")

    # ── Flags row ────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Over cost budget", summary["over_cost_budget"],
              help="Requests whose estimated cost exceeded ENERGY_ADVISOR_MAX_REQUEST_COST_USD.")
    f2.metric("Over latency budget", summary["over_latency_budget"],
              help="Requests slower than ENERGY_ADVISOR_MAX_REQUEST_LATENCY_S.")
    f3.metric("Out of scope", summary["out_of_scope"],
              help="Questions flagged by the AgentContract topicality check.")
    f4.metric("Errors", sum(summary["errors"].values()),
              help="Failed requests, grouped below by error type.")

    st.divider()

    col_left, col_right = st.columns([1.2, 1], gap="large")
    with col_left:
        st.plotly_chart(_chart_daily(summary["by_day"]), width="stretch")
    with col_right:
        st.plotly_chart(_chart_top_tools(summary["top_tools"]), width="stretch")

    # ── Provenance + models + errors ─────────────────────────────────
    st.divider()
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("**Cost provenance**")
        st.caption("`usage_metadata` = real provider tokens · `heuristic` = chars/4 fallback")
        for source, count in summary["by_cost_source"].items():
            st.markdown(f"- `{source}`: {count}")
    with p2:
        st.markdown("**By model**")
        for model, bucket in summary["by_model"].items():
            st.markdown(f"- `{model}`: {bucket['requests']} req · ${bucket['cost_usd']:.4f}")
    with p3:
        st.markdown("**Errors**")
        if summary["errors"]:
            for label, count in summary["errors"].items():
                short = label if len(label) <= 60 else label[:57] + "…"
                st.markdown(f"- `{short}`: {count}")
        else:
            st.caption("No errors recorded. 🎉")

    # ── Recent traces drill-down ─────────────────────────────────────
    with st.expander("🔍 Last 20 traces (raw)"):
        recent = sorted(
            traces, key=lambda t: t.get("created_at_epoch_s", 0.0), reverse=True
        )[:20]
        frame = pd.DataFrame([
            {
                "request_id": t.get("request_id", "")[:8],
                "success": t.get("success"),
                "latency_s": t.get("latency_s"),
                "cost_usd": t.get("estimated_cost_usd"),
                "cost_source": t.get("cost_source"),
                "tools": ", ".join(t.get("tools_used", [])),
                "error": (t.get("error") or "")[:40],
            }
            for t in recent
        ])
        st.dataframe(frame, width="stretch", hide_index=True)
