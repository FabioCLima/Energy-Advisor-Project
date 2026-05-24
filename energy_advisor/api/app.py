from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langserve import add_routes
from pydantic import BaseModel, Field

from energy_advisor import EnergyAdvisorAgent


class AdvisorRequest(BaseModel):
    """HTTP request payload for single-turn agent calls."""

    question: str = Field(..., description="Natural-language question from the user.")
    context: str | None = Field(None, description="Optional extra context or constraints.")

    # Optional identifiers used only for observability (LangSmith tags/metadata).
    user_id: str | None = Field(None, description="Optional user identifier for tracing.")
    session_id: str | None = Field(None, description="Optional session identifier for tracing.")
    request_id: str | None = Field(None, description="Optional request identifier for tracing.")


_agent: EnergyAdvisorAgent | None = None


def _get_agent() -> EnergyAdvisorAgent:
    global _agent
    if _agent is None:
        _agent = EnergyAdvisorAgent()
    return _agent


def _merge_trace_config(inp: AdvisorRequest, base: RunnableConfig | None) -> RunnableConfig:
    cfg: dict[str, Any] = dict(base or {})

    tags = list(cfg.get("tags", []))
    tags.extend(["app:energy_advisor", "surface:langserve"])
    if inp.user_id:
        tags.append(f"user:{inp.user_id}")
    if inp.session_id:
        tags.append(f"session:{inp.session_id}")
    cfg["tags"] = tags

    metadata = dict(cfg.get("metadata", {}))
    if inp.user_id:
        metadata["user_id"] = inp.user_id
    if inp.session_id:
        metadata["session_id"] = inp.session_id
    if inp.request_id:
        metadata["request_id"] = inp.request_id
    cfg["metadata"] = metadata

    cfg.setdefault("run_name", "EnergyAdvisorAgent")
    return cfg  # type: ignore[return-value]


def _advisor(inp: AdvisorRequest, config: RunnableConfig | None = None) -> Iterator[str]:
    """Runnable entrypoint.

    Implemented as a generator so LangServe can stream tokens via SSE.
    RunnableLambda.invoke() will consume the generator and return the full string.
    """
    agent = _get_agent()
    trace_config = _merge_trace_config(inp, config)
    yield from agent.stream(inp.question, context=inp.context, config=trace_config)


app = FastAPI(
    title="EcoHome Energy Advisor API",
    version="0.1.0",
    description="FastAPI + LangServe wrapper around the EcoHome Energy Advisor (LangGraph ReAct).",
)

# Streamlit community cloud and local frontends benefit from permissive CORS.
# Tighten this list for production deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"] ,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Expose the agent runnable under /advisor/* (invoke/stream/batch/etc.).
add_routes(
    app,
    RunnableLambda(_advisor).with_types(input_type=AdvisorRequest, output_type=str),
    path="/advisor",
)
