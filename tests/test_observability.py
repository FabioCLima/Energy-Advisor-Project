from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage

from energy_advisor.observability import (
    AgentTrace,
    TraceRecorder,
    build_agent_trace,
    cost_from_tokens,
    estimate_llm_cost,
    estimate_tokens,
    extract_token_usage,
    extract_tool_call_details,
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


def test_estimate_llm_cost_declares_heuristic_source() -> None:
    assert estimate_llm_cost("gpt-4o-mini", "abc", "def").cost_source == "heuristic"


# ── A-4: real token accounting ────────────────────────────────────────

def test_cost_from_tokens_uses_pricing_table() -> None:
    estimate = cost_from_tokens("gpt-4o-mini", 1000, 500)

    assert estimate.estimated_cost_usd == 0.00045
    assert estimate.cost_source == "usage_metadata"


def test_cost_from_tokens_accepts_pricing_override() -> None:
    estimate = cost_from_tokens("my-model", 1000, 1000, pricing={"my-model": (0.01, 0.02)})

    assert estimate.estimated_cost_usd == 0.03


def test_extract_token_usage_sums_every_llm_iteration() -> None:
    result = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "c1", "name": "t", "args": {}}],
                usage_metadata={"input_tokens": 700, "output_tokens": 30, "total_tokens": 730},
            ),
            ToolMessage(content="data", tool_call_id="c1", name="t"),
            AIMessage(
                content="final",
                usage_metadata={"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020},
            ),
        ]
    }

    assert extract_token_usage(result) == (1600, 150)


def test_extract_token_usage_returns_none_without_metadata() -> None:
    result = {"messages": [AIMessage(content="no usage")]}

    assert extract_token_usage(result) is None


def test_build_agent_trace_prefers_usage_metadata_over_heuristic() -> None:
    result = {
        "messages": [
            AIMessage(
                content="final answer",
                usage_metadata={"input_tokens": 2000, "output_tokens": 400, "total_tokens": 2400},
            )
        ]
    }

    trace = build_agent_trace(
        question="short q",
        result=result,
        model="gpt-4o-mini",
        latency_s=1.0,
        max_cost_usd=0.01,
        max_latency_s=20.0,
    )

    assert trace.cost_source == "usage_metadata"
    assert trace.input_tokens == 2000
    assert trace.output_tokens == 400


def test_build_agent_trace_falls_back_to_heuristic() -> None:
    trace = build_agent_trace(
        question="short q",
        result={"messages": [AIMessage(content="plain")]},
        model="gpt-4o-mini",
        latency_s=1.0,
        max_cost_usd=0.01,
        max_latency_s=20.0,
    )

    assert trace.cost_source == "heuristic"


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


# ── session_id tests (O-1) ────────────────────────────────────────────

def test_build_agent_trace_stores_session_id() -> None:
    trace = build_agent_trace(
        question="test question",
        result=None,
        model="gpt-4o-mini",
        latency_s=1.0,
        max_cost_usd=0.01,
        max_latency_s=20.0,
        session_id="sess-abc-123",
    )

    assert trace.session_id == "sess-abc-123"


def test_build_agent_trace_session_id_defaults_to_none() -> None:
    trace = build_agent_trace(
        question="test question",
        result=None,
        model="gpt-4o-mini",
        latency_s=1.0,
        max_cost_usd=0.01,
        max_latency_s=20.0,
    )

    assert trace.session_id is None


def test_trace_recorder_persists_session_id(tmp_path) -> None:
    import json

    trace_path = tmp_path / "traces.jsonl"
    recorder = TraceRecorder(str(trace_path))
    trace = AgentTrace(
        request_id="req-2",
        model="gpt-4o-mini",
        question_chars=10,
        answer_chars=20,
        latency_s=0.5,
        tools_used=[],
        success=True,
        session_id="sess-xyz-789",
    )

    recorder.record(trace)

    payload = json.loads(trace_path.read_text(encoding="utf-8").strip())
    assert payload["session_id"] == "sess-xyz-789"


# ── Tool call detail tests (O-2) ──────────────────────────────────────

def _make_langgraph_result() -> dict:
    """Minimal LangGraph state with one tool call and its response."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call-1", "name": "query_energy_usage", "args": {"days": 30}}],
    )
    tool_msg = ToolMessage(
        content='{"total_kwh": 120.5}',
        tool_call_id="call-1",
        name="query_energy_usage",
    )
    final_msg = AIMessage(content="Your usage was 120.5 kWh.")
    return {"messages": [ai_msg, tool_msg, final_msg]}


def test_extract_tool_call_details_returns_name_and_args() -> None:
    result = _make_langgraph_result()
    details = extract_tool_call_details(result)

    assert len(details) == 1
    assert details[0].name == "query_energy_usage"
    assert details[0].args == {"days": 30}


def test_extract_tool_call_details_captures_response_chars() -> None:
    result = _make_langgraph_result()
    details = extract_tool_call_details(result)

    assert details[0].response_chars == len('{"total_kwh": 120.5}')


def test_extract_tool_call_details_empty_on_no_tool_calls() -> None:
    result = {"messages": [AIMessage(content="Just a direct answer.")]}
    assert extract_tool_call_details(result) == []


def test_build_agent_trace_populates_tool_calls_detail() -> None:
    result = _make_langgraph_result()
    trace = build_agent_trace(
        question="How much did I use?",
        result=result,
        model="gpt-4o-mini",
        latency_s=1.5,
        max_cost_usd=0.01,
        max_latency_s=20.0,
    )

    assert len(trace.tool_calls_detail) == 1
    assert trace.tool_calls_detail[0].name == "query_energy_usage"
    assert trace.tool_calls_detail[0].args == {"days": 30}


def test_tool_calls_detail_serialised_to_jsonl(tmp_path) -> None:
    result = _make_langgraph_result()
    trace = build_agent_trace(
        question="How much?",
        result=result,
        model="gpt-4o-mini",
        latency_s=1.0,
        max_cost_usd=0.01,
        max_latency_s=20.0,
        request_id="req-detail",
    )
    recorder = TraceRecorder(str(tmp_path / "t.jsonl"))
    recorder.record(trace)

    payload = json.loads((tmp_path / "t.jsonl").read_text())
    detail = payload["tool_calls_detail"]
    assert len(detail) == 1
    assert detail[0]["name"] == "query_energy_usage"
    assert detail[0]["args"] == {"days": 30}
    assert detail[0]["response_chars"] == len('{"total_kwh": 120.5}')
