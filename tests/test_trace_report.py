"""Trace reader tests — JSONL aggregation and rotation."""
from __future__ import annotations

import json
import time

from energy_advisor.observability import AgentTrace, TraceRecorder
from energy_advisor.observability.report import load_traces, render_summary, summarize_traces


def _trace(**overrides) -> dict:
    base = {
        "request_id": "r1",
        "model": "gpt-4o-mini",
        "latency_s": 2.0,
        "estimated_cost_usd": 0.002,
        "cost_source": "usage_metadata",
        "success": True,
        "error": None,
        "tools_used": ["query_energy_usage"],
        "over_cost_budget": False,
        "over_latency_budget": False,
        "metadata": {},
        "created_at_epoch_s": time.time(),
    }
    base.update(overrides)
    return base


def test_summarize_aggregates_costs_latency_and_errors() -> None:
    traces = [
        _trace(),
        _trace(latency_s=10.0, estimated_cost_usd=0.01, tools_used=["get_electricity_prices"]),
        _trace(success=False, error="recursion_limit"),
        _trace(metadata={"scope_check": "out_of_scope"}),
    ]

    summary = summarize_traces(traces)

    assert summary["total_requests"] == 4
    assert summary["success_rate"] == 0.75
    assert summary["total_cost_usd"] == 0.016
    assert summary["errors"] == {"recursion_limit": 1}
    assert summary["out_of_scope"] == 1
    assert summary["by_cost_source"]["usage_metadata"] == 4
    assert summary["top_tools"]["query_energy_usage"] == 3


def test_summarize_groups_by_day_and_model() -> None:
    summary = summarize_traces([_trace(), _trace(model="gpt-4o", estimated_cost_usd=0.05)])

    assert summary["by_model"]["gpt-4o-mini"]["requests"] == 1
    assert summary["by_model"]["gpt-4o"]["cost_usd"] == 0.05
    assert len(summary["by_day"]) == 1


def test_render_summary_handles_empty_traces() -> None:
    assert render_summary(summarize_traces([])) == "No traces found."


def test_load_traces_skips_corrupt_lines(tmp_path) -> None:
    path = tmp_path / "traces.jsonl"
    path.write_text(json.dumps(_trace()) + "\n{not json}\n" + json.dumps(_trace()) + "\n")

    assert len(load_traces(path)) == 2


def test_load_traces_missing_file_returns_empty(tmp_path) -> None:
    assert load_traces(tmp_path / "nope.jsonl") == []


# ── E-5: size-based rotation ──────────────────────────────────────────

def _record(recorder: TraceRecorder) -> None:
    recorder.record(AgentTrace(
        request_id="r", model="gpt-4o-mini", question_chars=10, answer_chars=10,
        latency_s=1.0, tools_used=[], success=True,
    ))


def test_trace_recorder_rotates_when_size_exceeded(tmp_path) -> None:
    path = tmp_path / "traces.jsonl"
    recorder = TraceRecorder(str(path), max_bytes=200)  # ~1 trace per file

    _record(recorder)
    _record(recorder)  # first write pushed size past 200 → rotates before this

    backup = tmp_path / "traces.jsonl.1"
    assert backup.exists()
    assert len(path.read_text().strip().splitlines()) == 1


def test_trace_recorder_no_rotation_when_disabled(tmp_path) -> None:
    path = tmp_path / "traces.jsonl"
    recorder = TraceRecorder(str(path), max_bytes=None)

    for _ in range(5):
        _record(recorder)

    assert not (tmp_path / "traces.jsonl.1").exists()
    assert len(path.read_text().strip().splitlines()) == 5
