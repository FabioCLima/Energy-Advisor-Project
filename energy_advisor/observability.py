"""Local observability primitives for the EcoHome agent.

The module intentionally avoids external services. LangSmith/OpenTelemetry can be
added later, but these helpers make traces and budget signals available in local
runs, Streamlit Cloud and Docker.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

_MODEL_PRICING_USD_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o": (0.00500, 0.01500),
}


class BudgetExceeded(RuntimeError):
    """Raised mid-run when accumulated LLM cost crosses the request budget.

    Operational counterpart of GuardrailViolation: same AUDIT/BLOCK rollout
    pattern, but protecting cost instead of content. The API maps it to 429.
    """


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool invocation captured from LangGraph message history."""

    name: str
    args: dict[str, Any]
    response_chars: int


@dataclass(frozen=True)
class CostEstimate:
    """Token and cost estimate for a single LLM request.

    cost_source declares provenance: "usage_metadata" means tokens were reported
    by the provider for every LLM call in the run (including ReAct iterations);
    "heuristic" means a chars/4 fallback over question + final answer only —
    a significant underestimate for agent runs.
    """

    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    cost_source: str = "heuristic"


@dataclass(frozen=True)
class AgentTrace:
    """Structured trace for one agent invocation."""

    request_id: str
    model: str
    question_chars: int
    answer_chars: int
    latency_s: float
    tools_used: list[str]
    success: bool
    error: str | None = None
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    over_cost_budget: bool = False
    over_latency_budget: bool = False
    cost_source: str = "heuristic"
    tool_calls_detail: list[ToolCallRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at_epoch_s: float = field(default_factory=time.time)


class TraceRecorder:
    """Append-only JSONL recorder for local agent traces."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def record(self, trace: AgentTrace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(trace), ensure_ascii=False, sort_keys=True) + "\n")


def new_request_id() -> str:
    return str(uuid.uuid4())


def estimate_tokens(text: str) -> int:
    """Return a deterministic rough token estimate using a chars/4 heuristic."""
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def _resolve_pricing(
    model: str, pricing: dict[str, tuple[float, float]] | None = None
) -> tuple[float, float]:
    table = {**_MODEL_PRICING_USD_PER_1K_TOKENS, **(pricing or {})}
    return table.get(model, (0.001, 0.002))


def cost_from_tokens(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    pricing: dict[str, tuple[float, float]] | None = None,
    cost_source: str = "usage_metadata",
) -> CostEstimate:
    """Compute cost from known token counts (e.g. provider usage_metadata)."""
    input_price, output_price = _resolve_pricing(model, pricing)
    cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=round(cost, 8),
        cost_source=cost_source,
    )


def estimate_llm_cost(
    model: str,
    input_text: str,
    output_text: str,
    *,
    pricing: dict[str, tuple[float, float]] | None = None,
) -> CostEstimate:
    """Heuristic fallback (chars/4 over question + final answer only).

    Underestimates agent runs: it ignores the system prompt, tool messages and
    every intermediate ReAct iteration. Prefer extract_token_usage + cost_from_tokens
    whenever the provider reports usage_metadata.
    """
    return cost_from_tokens(
        model,
        estimate_tokens(input_text),
        estimate_tokens(output_text),
        pricing=pricing,
        cost_source="heuristic",
    )


def extract_token_usage(result: dict[str, Any]) -> tuple[int, int] | None:
    """Sum provider-reported token usage across every AIMessage in the run.

    Returns (input_tokens, output_tokens), or None when no message carries
    usage_metadata (e.g. fake models in tests) so callers can fall back to
    the heuristic — with cost_source declaring which path was taken.
    """
    input_tokens = 0
    output_tokens = 0
    found = False
    for msg in result.get("messages", []):
        usage = getattr(msg, "usage_metadata", None)
        if isinstance(msg, AIMessage) and usage:
            input_tokens += int(usage.get("input_tokens", 0))
            output_tokens += int(usage.get("output_tokens", 0))
            found = True
    return (input_tokens, output_tokens) if found else None


def extract_tool_calls(result: dict[str, Any]) -> list[str]:
    """Return tool names called by a LangGraph result in execution order."""
    called: list[str] = []
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            called.extend(tc["name"] for tc in msg.tool_calls)
    return called


def extract_tool_call_details(result: dict[str, Any]) -> list[ToolCallRecord]:
    """Return one ToolCallRecord per tool invocation, with args and response size.

    Pairs each AIMessage.tool_calls entry with its ToolMessage response via
    tool_call_id, so args and response_chars travel together in the trace.
    """
    messages = result.get("messages", [])

    # Build map: tool_call_id → number of chars in the tool response
    response_chars: dict[str, int] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            response_chars[msg.tool_call_id] = len(str(msg.content))

    records: list[ToolCallRecord] = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                records.append(ToolCallRecord(
                    name=tc["name"],
                    args=dict(tc.get("args") or {}),
                    response_chars=response_chars.get(tc["id"], 0),
                ))
    return records


def extract_final_answer(result: dict[str, Any]) -> str:
    """Return the final assistant answer from a LangGraph result."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return str(msg.content)
    return ""


def build_agent_trace(
    *,
    question: str,
    result: dict[str, Any] | None,
    model: str,
    latency_s: float,
    max_cost_usd: float,
    max_latency_s: float,
    request_id: str | None = None,
    session_id: str | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
    pricing: dict[str, tuple[float, float]] | None = None,
) -> AgentTrace:
    resolved_result = result or {}
    final_answer = extract_final_answer(resolved_result)
    usage = extract_token_usage(resolved_result)
    if usage is not None:
        cost = cost_from_tokens(model, usage[0], usage[1], pricing=pricing)
    else:
        cost = estimate_llm_cost(model, question, final_answer, pricing=pricing)
    return AgentTrace(
        request_id=request_id or new_request_id(),
        model=model,
        question_chars=len(question),
        answer_chars=len(final_answer),
        latency_s=round(latency_s, 4),
        tools_used=extract_tool_calls(resolved_result),
        success=error is None,
        error=error,
        session_id=session_id,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        estimated_cost_usd=cost.estimated_cost_usd,
        over_cost_budget=cost.estimated_cost_usd > max_cost_usd,
        over_latency_budget=latency_s > max_latency_s,
        cost_source=cost.cost_source,
        tool_calls_detail=extract_tool_call_details(resolved_result),
        metadata=metadata or {},
    )
