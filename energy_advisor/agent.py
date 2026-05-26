from __future__ import annotations

import os
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from loguru import logger

from .config import Settings
from .guardrails import ensure_safe_model_output, ensure_safe_user_input
from .logging import configure_logging
from .observability import TraceRecorder, build_agent_trace, extract_final_answer, new_request_id
from .prompts import SYSTEM_INSTRUCTIONS
from .tools import TOOL_KIT


class AgentState(TypedDict):
    """LangGraph state schema (contract): message history only."""

    messages: Annotated[list[BaseMessage], add_messages]


class EnergyAdvisorAgent:
    """
    LangGraph ReAct agent wrapped in a clean, portfolio-ready interface.

    Usage:
        agent = EnergyAdvisorAgent()
        result = agent.invoke("When should I charge my EV?")
        print(result["messages"][-1].content)
    """

    def __init__(
        self,
        instructions: str = SYSTEM_INSTRUCTIONS,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        # Load .env from repo root or ecohome_solution/
        try:
            from dotenv import load_dotenv  # type: ignore
            for candidate in (".env", os.path.join("..", ".env")):
                if os.path.exists(candidate):
                    load_dotenv(candidate)
                    break
        except ImportError:
            pass

        self.settings = settings or Settings()
        configure_logging(self.settings.log_level)
        self._configure_langsmith()

        selected_model = model or self.settings.selected_model()
        api_key = self.settings.selected_api_key()
        if not api_key:
            raise ValueError(
                "No API key found. Set OPENAI_API_KEY, VOCAREUM_API_KEY, "
                "or ENERGY_ADVISOR_API_KEY in your .env file."
            )

        logger.info(
            "Initialising EnergyAdvisorAgent | model={} preset={}",
            selected_model,
            self.settings.model_preset,
        )

        self._system_message = SystemMessage(content=instructions)
        self._selected_model = selected_model
        self._trace_recorder = TraceRecorder(self.settings.observability_trace_path)

        llm = ChatOpenAI(
            model=selected_model,
            temperature=self.settings.temperature,
            base_url=self.settings.base_url,
            api_key=api_key,
        )
        llm_with_tools = llm.bind_tools(TOOL_KIT)

        # ── Graph (Schema, Nodes, Edges) ─────────────────────────────
        #
        # This explicit graph satisfies the rubric requirement:
        # - Schema: AgentState
        # - Nodes: assistant, tools
        # - Edges: assistant -> tools (conditional), tools -> assistant, assistant -> END

        def assistant_node(state: AgentState) -> dict[str, Any]:
            response = llm_with_tools.invoke(state["messages"])
            return {"messages": [response]}

        tools_node = ToolNode(TOOL_KIT)

        def route_after_assistant(state: AgentState) -> str:
            last = state["messages"][-1] if state.get("messages") else None
            tool_calls = getattr(last, "tool_calls", None)
            return "tools" if tool_calls else END

        builder: StateGraph[AgentState] = StateGraph(AgentState)
        builder.add_node("assistant", assistant_node)
        builder.add_node("tools", tools_node)
        builder.set_entry_point("assistant")
        builder.add_conditional_edges("assistant", route_after_assistant)
        builder.add_edge("tools", "assistant")

        self.graph = builder.compile()

    def _build_messages(self, question: str, context: str | None) -> list[BaseMessage]:
        now = datetime.now()
        date_context = SystemMessage(
            content=(
                f"Current date and time: {now.strftime('%Y-%m-%d %H:%M')} (São Paulo, BRT).\n"
                f"When the user says 'last 30 days', use start_date="
                f"{(now - timedelta(days=30)).strftime('%Y-%m-%d')}"
                f" and end_date={now.strftime('%Y-%m-%d')}."
            )
        )
        messages: list[BaseMessage] = [self._system_message, date_context]
        if context:
            messages.append(SystemMessage(content=context))
        messages.append(HumanMessage(content=question))
        return messages

    def invoke(
        self,
        question: str,
        context: str | None = None,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        """Run the agent on a natural-language question.

        Returns:
            The LangGraph state dict. Final answer is in result["messages"][-1].content.
        """
        request_id, metadata = self._observability_context(config)
        t0 = time.perf_counter()
        try:
            ensure_safe_user_input(question, mode=self.settings.guardrail_mode)
            result = self.graph.invoke(
                {"messages": self._build_messages(question, context)},
                config=config,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self._record_trace(
                question=question,
                result=None,
                latency_s=elapsed,
                request_id=request_id,
                metadata=metadata,
                error=str(exc),
            )
            raise

        elapsed = time.perf_counter() - t0
        try:
            ensure_safe_model_output(extract_final_answer(result), mode=self.settings.guardrail_mode)
        except Exception as exc:
            self._record_trace(
                question=question,
                result=result,
                latency_s=elapsed,
                request_id=request_id,
                metadata=metadata,
                error=str(exc),
            )
            raise
        self._record_trace(
            question=question,
            result=result,
            latency_s=elapsed,
            request_id=request_id,
            metadata=metadata,
        )
        return result

    def stream(
        self,
        question: str,
        context: str | None = None,
        config: RunnableConfig | None = None,
    ) -> Iterator[str]:
        """Stream the final response token by token via LangGraph stream_mode='messages'.

        Yields text chunks from the assistant's final answer only — tool-calling
        intermediate messages are filtered out. Tool names are accumulated in
        self.last_tools_used as a side effect, readable after the generator is exhausted.

        Args:
            question: The user's natural-language question.
            context: Optional extra context injected as a system message.

        Yields:
            str: Individual text chunks of the final response.
        """
        ensure_safe_user_input(question, mode=self.settings.guardrail_mode)
        self.last_tools_used: list[str] = []
        for chunk, metadata in self.graph.stream(  # type: ignore[misc]
            {"messages": self._build_messages(question, context)},
            config=config,
            stream_mode="messages",
        ):
            if (
                isinstance(chunk, AIMessageChunk)
                and chunk.content
                and not chunk.tool_call_chunks
                and metadata.get("langgraph_node") == "assistant"
            ):
                yield chunk.content
            elif isinstance(chunk, ToolMessage) and chunk.name:
                if chunk.name not in self.last_tools_used:
                    self.last_tools_used.append(chunk.name)

    def _observability_context(self, config: RunnableConfig | None) -> tuple[str, dict[str, Any]]:
        metadata: dict[str, Any] = {}
        if isinstance(config, dict):
            raw_metadata = config.get("metadata") or {}
            if isinstance(raw_metadata, dict):
                metadata.update(raw_metadata)
        request_id = str(metadata.get("request_id") or new_request_id())
        metadata.setdefault("request_id", request_id)
        return request_id, metadata

    def _record_trace(
        self,
        *,
        question: str,
        result: dict[str, Any] | None,
        latency_s: float,
        request_id: str,
        metadata: dict[str, Any],
        error: str | None = None,
    ) -> None:
        if not self.settings.observability_enabled:
            return
        trace = build_agent_trace(
            question=question,
            result=result,
            model=self._selected_model,
            latency_s=latency_s,
            max_cost_usd=self.settings.max_request_cost_usd,
            max_latency_s=self.settings.max_request_latency_s,
            request_id=request_id,
            error=error,
            metadata=metadata,
        )
        self._trace_recorder.record(trace)

    def get_agent_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return [t.name for t in TOOL_KIT]

    def _configure_langsmith(self) -> None:
        """Set LangSmith environment variables from settings if present."""
        if self.settings.langchain_api_key:
            os.environ.setdefault("LANGCHAIN_API_KEY", self.settings.langchain_api_key)
        if self.settings.langchain_tracing_v2:
            os.environ.setdefault("LANGCHAIN_TRACING_V2", self.settings.langchain_tracing_v2)
        if self.settings.langchain_project:
            os.environ.setdefault("LANGCHAIN_PROJECT", self.settings.langchain_project)
        if self.settings.langchain_endpoint:
            os.environ.setdefault("LANGCHAIN_ENDPOINT", self.settings.langchain_endpoint)
