from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from loguru import logger
from pydantic import BaseModel, Field

from energy_advisor import EnergyAdvisorAgent
from energy_advisor.bootstrap.runtime import ensure_demo_assets
from energy_advisor.config import Settings
from energy_advisor.guardrails import GuardrailViolation
from energy_advisor.observability import BudgetExceeded, new_request_id


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
if settings.bootstrap_on_start:
    ensure_demo_assets(settings=settings, ensure_vectorstore_index=settings.bootstrap_vectorstore)

app = FastAPI(
    title="EcoHome Energy Advisor API",
    version="0.4.0",
    description=(
        "FastAPI wrapper around the EcoHome Energy Advisor (LangGraph ReAct). "
        "POST /advisor/invoke for a full response; POST /advisor/stream for SSE token streaming."
    ),
)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Service-boundary dependencies: auth + rate limit ─────────────────

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def require_api_key(request: Request) -> None:
    """Reject /advisor/* calls without the configured X-API-Key header."""
    if not settings.api_auth_key:
        return
    provided = request.headers.get("X-API-Key")
    if provided != settings.api_auth_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")


def enforce_rate_limit(request: Request) -> None:
    """In-memory sliding-window limiter per client IP (per instance)."""
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_windows[client_ip]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
    window.append(now)


advisor_dependencies = [Depends(require_api_key), Depends(enforce_rate_limit)]


def _internal_error(request_id: str, exc: Exception) -> HTTPException:
    """Map unexpected errors to a 500 without leaking internals.

    The real exception goes to the log, correlated by request_id — the same id
    recorded in the agent trace, so an operator can join both.
    """
    logger.exception("Unhandled API error | request_id={} | {}", request_id, exc)
    return HTTPException(
        status_code=500,
        detail=f"Internal error. Reference request_id={request_id}.",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/advisor/invoke", response_model=AdvisorResponse, dependencies=advisor_dependencies)
def invoke(req: AdvisorRequest) -> AdvisorResponse:
    """Run the agent synchronously and return the final answer."""
    request_id = req.request_id or new_request_id()
    req.request_id = request_id
    try:
        agent = _get_agent()
        result = agent.invoke(req.question, context=req.context, config=_build_config(req))
    except GuardrailViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise _internal_error(request_id, exc) from exc

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


@app.post("/advisor/stream", dependencies=advisor_dependencies)
def stream(req: AdvisorRequest) -> StreamingResponse:
    """Stream the agent response token-by-token via Server-Sent Events (SSE).

    Each event carries a JSON payload: {"text": "<chunk>"}.
    The stream terminates with the sentinel event: data: [DONE]
    """
    request_id = req.request_id or new_request_id()
    req.request_id = request_id

    def _generate() -> Iterator[str]:
        try:
            agent = _get_agent()
            for chunk in agent.stream(req.question, context=req.context, config=_build_config(req)):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except GuardrailViolation as exc:
            yield f"data: {json.dumps({'error': str(exc), 'status_code': 400})}\n\n"
        except BudgetExceeded as exc:
            yield f"data: {json.dumps({'error': str(exc), 'status_code': 429})}\n\n"
        except Exception as exc:
            logger.exception("Unhandled stream error | request_id={} | {}", request_id, exc)
            yield (
                "data: "
                + json.dumps({"error": f"Internal error. Reference request_id={request_id}."})
                + "\n\n"
            )
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
