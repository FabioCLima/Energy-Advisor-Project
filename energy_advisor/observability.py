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

from langchain_core.messages import AIMessage

_MODEL_PRICING_USD_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o": (0.00500, 0.01500),
}


@dataclass(frozen=True)
class CostEstimate:
    """Approximate token and cost estimate for a single LLM request."""

    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


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
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    over_cost_budget: bool = False
    over_latency_budget: bool = False
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


def estimate_llm_cost(model: str, input_text: str, output_text: str) -> CostEstimate:
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    input_price, output_price = _MODEL_PRICING_USD_PER_1K_TOKENS.get(model, (0.001, 0.002))
    cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=round(cost, 8),
    )


def extract_tool_calls(result: dict[str, Any]) -> list[str]:
    """Return tool names called by a LangGraph result in execution order."""
    called: list[str] = []
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            called.extend(tc["name"] for tc in msg.tool_calls)
    return called


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
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentTrace:
    final_answer = extract_final_answer(result or {})
    cost = estimate_llm_cost(model, question, final_answer)
    return AgentTrace(
        request_id=request_id or new_request_id(),
        model=model,
        question_chars=len(question),
        answer_chars=len(final_answer),
        latency_s=round(latency_s, 4),
        tools_used=extract_tool_calls(result or {}),
        success=error is None,
        error=error,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        estimated_cost_usd=cost.estimated_cost_usd,
        over_cost_budget=cost.estimated_cost_usd > max_cost_usd,
        over_latency_budget=latency_s > max_latency_s,
        metadata=metadata or {},
    )
