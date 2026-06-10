"""Operations tab chart builders — pure figure construction, no Streamlit runtime."""
from __future__ import annotations

import plotly.graph_objects as go

from app.components.operations import _chart_daily, _chart_top_tools


def test_chart_daily_has_requests_bar_and_cost_line() -> None:
    by_day = {
        "2026-06-09": {"requests": 10, "errors": 1, "cost_usd": 0.05, "avg_latency_s": 8.0},
        "2026-06-10": {"requests": 20, "errors": 0, "cost_usd": 0.12, "avg_latency_s": 9.5},
    }

    fig = _chart_daily(by_day)

    assert isinstance(fig, go.Figure)
    types = {trace.type for trace in fig.data}
    assert types == {"bar", "scatter"}
    assert list(fig.data[0].y) == [10, 20]


def test_chart_top_tools_orders_horizontal_bars() -> None:
    fig = _chart_top_tools({"query_energy_usage": 34, "get_weather_forecast": 15})

    assert isinstance(fig, go.Figure)
    assert fig.data[0].orientation == "h"
    # sorted ascending so the biggest bar renders on top
    assert list(fig.data[0].x) == [15, 34]
