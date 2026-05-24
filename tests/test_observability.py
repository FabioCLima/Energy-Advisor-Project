from __future__ import annotations

import json

from energy_advisor.observability import (
    AgentTrace,
    TraceRecorder,
    build_agent_trace,
    estimate_llm_cost,
    estimate_tokens,
)


def test_estimate_tokens_is_deterministic_and_nonzero_for_text() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 0


def test_estimate_llm_cost_uses_known_model_pricing() -> None:
    estimate = estimate_llm_cost("gpt-4o-mini", "a" * 4000, "b" * 2000)

    assert estimate.input_tokens == 1000
    assert estimate.output_tokens == 500
    assert estimate.estimated_cost_usd == 0.00045


def test_trace_recorder_writes_jsonl(tmp_path) -> None:
    trace_path = tmp_path / "traces.jsonl"
    recorder = TraceRecorder(str(trace_path))
    trace = AgentTrace(
        request_id="req-1",
        model="gpt-4o-mini",
        question_chars=12,
        answer_chars=34,
        latency_s=0.25,
        tools_used=["query_energy_usage"],
        success=True,
    )

    recorder.record(trace)

    line = trace_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["request_id"] == "req-1"
    assert payload["tools_used"] == ["query_energy_usage"]
    assert payload["success"] is True


def test_build_agent_trace_sets_budget_flags_without_langgraph_result() -> None:
    trace = build_agent_trace(
        question="a" * 4000,
        result=None,
        model="gpt-4o",
        latency_s=10.0,
        max_cost_usd=0.001,
        max_latency_s=5.0,
        request_id="req-budget",
        error="boom",
    )

    assert trace.request_id == "req-budget"
    assert trace.success is False
    assert trace.error == "boom"
    assert trace.over_cost_budget is True
    assert trace.over_latency_budget is True
