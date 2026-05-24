from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from energy_advisor import EnergyAdvisorAgent
from energy_advisor.bootstrap.runtime import ensure_demo_assets
from energy_advisor.config import Settings


class AdvisorRequest(BaseModel):
    """HTTP request payload for single-turn agent calls."""

    question: str = Field(..., description="Natural-language question from the user.")
    context: str | None = Field(None, description="Optional extra context or constraints.")

    user_id: str | None = Field(None, description="Optional user identifier for tracing.")
    session_id: str | None = Field(None, description="Optional session identifier for tracing.")
    request_id: str | None = Field(None, description="Optional request identifier for tracing.")


class AdvisorResponse(BaseModel):
    answer: str
    tools_used: list[str] = Field(default_factory=list)


_agent: EnergyAdvisorAgent | None = None


def _get_agent() -> EnergyAdvisorAgent:
    global _agent
    if _agent is None:
        _agent = EnergyAdvisorAgent()
    return _agent


def _build_config(req: AdvisorRequest) -> dict[str, Any]:
    tags = ["app:energy_advisor", "surface:api"]
    metadata: dict[str, Any] = {}
    if req.user_id:
        tags.append(f"user:{req.user_id}")
        metadata["user_id"] = req.user_id
    if req.session_id:
        tags.append(f"session:{req.session_id}")
        metadata["session_id"] = req.session_id
    if req.request_id:
        metadata["request_id"] = req.request_id
    return {"tags": tags, "metadata": metadata, "run_name": "EnergyAdvisorAgent"}


settings = Settings()
ensure_demo_assets(settings=settings, ensure_vectorstore_index=False)

app = FastAPI(
    title="EcoHome Energy Advisor API",
    version="0.3.0",
    description=(
        "FastAPI wrapper around the EcoHome Energy Advisor (LangGraph ReAct). "
        "POST /advisor/invoke for a full response; POST /advisor/stream for SSE token streaming."
    ),
)

# Restrict origins for production; permissive here for demo + Streamlit Cloud frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advisor/invoke", response_model=AdvisorResponse)
def invoke(req: AdvisorRequest) -> AdvisorResponse:
    """Run the agent synchronously and return the final answer."""
    try:
        agent = _get_agent()
        result = agent.invoke(req.question, context=req.context, config=_build_config(req))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    final_answer = next(
        (m.content for m in reversed(result.get("messages", []))
         if isinstance(m, AIMessage) and not m.tool_calls),
        "",
    )
    tools_used = [
        tc["name"]
        for m in result.get("messages", [])
        if isinstance(m, AIMessage)
        for tc in (m.tool_calls or [])
    ]
    return AdvisorResponse(answer=final_answer, tools_used=tools_used)


@app.post("/advisor/stream")
def stream(req: AdvisorRequest) -> StreamingResponse:
    """Stream the agent response token-by-token via Server-Sent Events (SSE).

    Each event carries a JSON payload: {"text": "<chunk>"}.
    The stream terminates with the sentinel event: data: [DONE]
    """
    def _generate() -> Iterator[str]:
        try:
            agent = _get_agent()
            for chunk in agent.stream(req.question, context=req.context, config=_build_config(req)):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
