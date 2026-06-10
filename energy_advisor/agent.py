from __future__ import annotations

import os
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from loguru import logger

from .config import Settings
from .contract import AgentContract
from .guardrails import (
    GuardrailMode,
    GuardrailViolation,
    ensure_safe_model_output,
    ensure_safe_user_input,
    validate_model_output,
)
from .logging import configure_logging
from .observability import (
    BudgetExceeded,
    TraceRecorder,
    build_agent_trace,
    cost_from_tokens,
    extract_final_answer,
    extract_token_usage,
    new_request_id,
)
from .prompts import SYSTEM_INSTRUCTIONS
from .tools import TOOL_KIT

# Honest fallback when the ReAct loop hits its iteration cap. The user gets a
# clear limitation statement instead of a GraphRecursionError stack trace.
RECURSION_FALLBACK_ANSWER = (
    "Não consegui concluir a análise dentro do limite de etapas configurado. "
    "Tente reformular a pergunta ou reduzir o escopo (por exemplo, um período "
    "ou dispositivo específico)."
)

# Friendly redirect when the contract's topicality check blocks a question.
SCOPE_REDIRECT_ANSWER = (
    "Eu sou o assistente de energia da EcoHome — posso ajudar com consumo, "
    "geração solar, carregamento do EV, tarifas, previsão e economia de "
    "energia da sua casa. Sobre esse assunto eu não consigo ajudar. "
    "Quer saber, por exemplo, qual o melhor horário para carregar o carro hoje?"
)


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

    Dependency injection (used by the test suite to run without API key/network):
        agent = EnergyAdvisorAgent(chat_model=fake_model, tools=[fake_tool])
    """

    def __init__(
        self,
        instructions: str = SYSTEM_INSTRUCTIONS,
        settings: Settings | None = None,
        model: str | None = None,
        contract: AgentContract | None = None,
        chat_model: BaseChatModel | None = None,
        tools: list[Any] | None = None,
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
        self.contract = contract or AgentContract.from_settings(self.settings)
        configure_logging(self.settings.log_level)
        self._configure_langsmith()

        selected_model = model or self.settings.selected_model()
        self._tools = tools if tools is not None else TOOL_KIT

        if chat_model is None:
            api_key = self.settings.selected_api_key()
            if not api_key:
                raise ValueError(
                    "No API key found. Set OPENAI_API_KEY, VOCAREUM_API_KEY, "
                    "or ENERGY_ADVISOR_API_KEY in your .env file."
                )
            chat_model = ChatOpenAI(
                model=selected_model,
                temperature=self.settings.temperature,
                base_url=self.settings.base_url,
                api_key=api_key,
                timeout=self.settings.llm_timeout_s,
                max_retries=self.settings.llm_max_retries,
                # Report token usage on the final chunk of streamed responses,
                # so cost accounting works for stream() as well as invoke().
                stream_usage=True,
            )

        logger.info(
            "Initialising EnergyAdvisorAgent | model={} preset={}",
            selected_model,
            self.settings.model_preset,
        )

        self._system_message = SystemMessage(content=instructions)
        self._selected_model = selected_model
        self._trace_recorder = TraceRecorder(self.settings.observability_trace_path)

        llm_with_tools = chat_model.bind_tools(self._tools)

        # ── Graph (Schema, Nodes, Edges) ─────────────────────────────
        #
        # This explicit graph satisfies the rubric requirement:
        # - Schema: AgentState
        # - Nodes: assistant, tools
        # - Edges: assistant -> tools (conditional), tools -> assistant, assistant -> END

        def assistant_node(state: AgentState) -> dict[str, Any]:
            response = llm_with_tools.invoke(state["messages"])
            self._enforce_cost_budget([*state["messages"], response])
            return {"messages": [response]}

        tools_node = ToolNode(self._tools)

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

        # In-memory checkpointer: conversation state per thread_id. A request
        # with session_id reuses its thread (multi-turn); without one, each
        # request gets a fresh thread keyed by request_id (single-turn, as
        # before). Per-process only — a multi-replica deployment would use a
        # persistent checkpointer (e.g. SqliteSaver/PostgresSaver).
        self.graph = builder.compile(checkpointer=MemorySaver())

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

    def _enforce_cost_budget(self, messages: list[BaseMessage]) -> None:
        """Interrupt the ReAct loop when accumulated cost crosses the budget.

        Checked after every LLM response — the point where a run can still be
        stopped before spending more. Requires provider usage_metadata; without
        it (heuristics only) enforcement would punish estimation error, so the
        check is skipped and over_cost_budget remains a post-hoc trace flag.
        """
        if self.settings.budget_mode != GuardrailMode.BLOCK:
            return
        usage = extract_token_usage({"messages": messages})
        if usage is None:
            return
        cost = cost_from_tokens(
            self._selected_model, usage[0], usage[1], pricing=self.settings.model_pricing()
        )
        if cost.estimated_cost_usd > self.settings.max_request_cost_usd:
            raise BudgetExceeded(
                f"Request budget exceeded: estimated ${cost.estimated_cost_usd:.6f} "
                f"> limit ${self.settings.max_request_cost_usd:.6f} "
                f"({usage[0]} input + {usage[1]} output tokens)."
            )

    def _runtime_config(self, config: RunnableConfig | None) -> RunnableConfig:
        """Merge caller config with the explicit ReAct iteration cap.

        One iteration = assistant step + tools step (2 graph super-steps),
        plus the final assistant step that produces the answer.
        """
        merged: dict[str, Any] = dict(config) if isinstance(config, dict) else {}
        merged.setdefault("recursion_limit", 2 * self.settings.max_agent_iterations + 1)
        return merged

    def _thread_input_and_config(
        self,
        question: str,
        context: str | None,
        config: RunnableConfig | None,
        *,
        request_id: str,
        session_id: str | None,
    ) -> tuple[dict[str, Any], RunnableConfig, bool]:
        """Resolve checkpointer thread and graph input for this turn.

        First turn of a thread gets the full system context; follow-up turns
        send only the new question — the checkpointer already holds the history.
        Returns (graph_input, config, has_history).
        """
        cfg = self._runtime_config(config)
        configurable = dict(cfg.get("configurable") or {})
        configurable.setdefault("thread_id", session_id or request_id)
        cfg["configurable"] = configurable

        existing = self.graph.get_state(cfg)
        has_history = bool(existing and existing.values.get("messages"))
        if has_history:
            messages: list[BaseMessage] = []
            if context:
                messages.append(SystemMessage(content=context))
            messages.append(HumanMessage(content=question))
        else:
            messages = self._build_messages(question, context)
        return {"messages": messages}, cfg, has_history

    def _check_scope_first_turn(
        self, question: str, has_history: bool, metadata: dict[str, Any]
    ) -> bool:
        """Run the contract topicality check on the first turn of a thread.

        Follow-up turns skip it: "e no fim de semana?" carries no domain
        keyword by nature — the conversation's scope was established on turn 1.

        Returns True when the question should be answered with the scope
        redirect instead of invoking the graph (BLOCK mode only). In AUDIT
        mode the violation is logged and flagged in trace metadata.
        """
        if has_history:
            return False
        result = self.contract.check_scope(question)
        if result.passed:
            return False
        metadata["scope_check"] = "out_of_scope"
        if self.contract.scope_mode == GuardrailMode.BLOCK:
            return True
        logger.warning("Scope audit — out-of-scope question: {}", question[:80])
        return False

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
        request_id, session_id, metadata = self._observability_context(config)
        t0 = time.perf_counter()
        try:
            ensure_safe_user_input(question, mode=self.contract.enforcement_mode)
            graph_input, cfg, has_history = self._thread_input_and_config(
                question, context, config, request_id=request_id, session_id=session_id
            )
            if self._check_scope_first_turn(question, has_history, metadata):
                result = {"messages": [AIMessage(content=SCOPE_REDIRECT_ANSWER)]}
                self._record_trace(
                    question=question,
                    result=result,
                    latency_s=time.perf_counter() - t0,
                    request_id=request_id,
                    session_id=session_id,
                    metadata=metadata,
                    error="out_of_scope",
                )
                return result
            result = self.graph.invoke(graph_input, config=cfg)
        except GraphRecursionError:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Agent hit max_agent_iterations={} | request_id={}",
                self.settings.max_agent_iterations,
                request_id,
            )
            result = {"messages": [AIMessage(content=RECURSION_FALLBACK_ANSWER)]}
            self._record_trace(
                question=question,
                result=result,
                latency_s=elapsed,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error="recursion_limit",
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self._record_trace(
                question=question,
                result=None,
                latency_s=elapsed,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error=str(exc),
            )
            raise

        elapsed = time.perf_counter() - t0
        try:
            ensure_safe_model_output(extract_final_answer(result), mode=self.contract.enforcement_mode)
        except Exception as exc:
            self._record_trace(
                question=question,
                result=result,
                latency_s=elapsed,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error=str(exc),
            )
            raise
        self._record_trace(
            question=question,
            result=result,
            latency_s=elapsed,
            request_id=request_id,
            session_id=session_id,
            metadata=metadata,
        )
        return result

    def stream(
        self,
        question: str,
        context: str | None = None,
        config: RunnableConfig | None = None,
    ) -> Iterator[str]:
        """Stream the final response token by token, under the same controls as invoke().

        Guardrails: the accumulated output is validated on every chunk. Streaming has
        no "final answer" to check before sending, so the trade-off is explicit —
        earlier chunks may already have reached the client, but the stream stops at
        the first violating chunk instead of leaking the rest.

        Observability: one AgentTrace is recorded per stream, same as invoke(),
        built from the final graph state (stream_mode "values").

        Yields text chunks from the assistant's final answer only — tool-calling
        intermediate messages are filtered out. Tool names are accumulated in
        self.last_tools_used as a side effect, readable after the generator is exhausted.
        """
        request_id, session_id, metadata = self._observability_context(config)
        t0 = time.perf_counter()
        try:
            ensure_safe_user_input(question, mode=self.contract.enforcement_mode)
        except Exception as exc:
            self._record_trace(
                question=question,
                result=None,
                latency_s=time.perf_counter() - t0,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error=str(exc),
            )
            raise

        self.last_tools_used: list[str] = []
        accumulated = ""
        last_state: dict[str, Any] | None = None
        audit_logged = False

        def _check_accumulated() -> None:
            nonlocal audit_logged
            check = validate_model_output(accumulated)
            if check.passed:
                return
            if self.contract.enforcement_mode == GuardrailMode.AUDIT:
                if not audit_logged:
                    logger.warning("AUDIT — Guardrail [stream-output] [{}] {}", check.severity, check.reason)
                    audit_logged = True
                return
            raise GuardrailViolation(check.reason or "Unsafe output rejected.")

        graph_input, cfg, has_history = self._thread_input_and_config(
            question, context, config, request_id=request_id, session_id=session_id
        )
        if self._check_scope_first_turn(question, has_history, metadata):
            self._record_trace(
                question=question,
                result={"messages": [AIMessage(content=SCOPE_REDIRECT_ANSWER)]},
                latency_s=time.perf_counter() - t0,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error="out_of_scope",
            )
            yield SCOPE_REDIRECT_ANSWER
            return
        try:
            for mode, payload in self.graph.stream(  # type: ignore[misc]
                graph_input,
                config=cfg,
                stream_mode=["messages", "values"],
            ):
                if mode == "values":
                    last_state = payload
                    continue
                chunk, chunk_meta = payload
                if (
                    isinstance(chunk, AIMessageChunk)
                    and chunk.content
                    and not chunk.tool_call_chunks
                    and chunk_meta.get("langgraph_node") == "assistant"
                ):
                    accumulated += chunk.content
                    _check_accumulated()
                    yield chunk.content
                elif isinstance(chunk, ToolMessage) and chunk.name:
                    if chunk.name not in self.last_tools_used:
                        self.last_tools_used.append(chunk.name)
        except GraphRecursionError:
            logger.warning(
                "Agent hit max_agent_iterations={} during stream | request_id={}",
                self.settings.max_agent_iterations,
                request_id,
            )
            self._record_trace(
                question=question,
                result=last_state,
                latency_s=time.perf_counter() - t0,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error="recursion_limit",
            )
            yield RECURSION_FALLBACK_ANSWER
            return
        except Exception as exc:
            self._record_trace(
                question=question,
                result=last_state,
                latency_s=time.perf_counter() - t0,
                request_id=request_id,
                session_id=session_id,
                metadata=metadata,
                error=str(exc),
            )
            raise

        self._record_trace(
            question=question,
            result=last_state,
            latency_s=time.perf_counter() - t0,
            request_id=request_id,
            session_id=session_id,
            metadata=metadata,
        )

    def _observability_context(
        self, config: RunnableConfig | None
    ) -> tuple[str, str | None, dict[str, Any]]:
        metadata: dict[str, Any] = {}
        if isinstance(config, dict):
            raw_metadata = config.get("metadata") or {}
            if isinstance(raw_metadata, dict):
                metadata.update(raw_metadata)
        request_id = str(metadata.get("request_id") or new_request_id())
        session_id = metadata.get("session_id") or None
        metadata.setdefault("request_id", request_id)
        return request_id, session_id, metadata

    def _record_trace(
        self,
        *,
        question: str,
        result: dict[str, Any] | None,
        latency_s: float,
        request_id: str,
        session_id: str | None = None,
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
            session_id=session_id,
            error=error,
            metadata=metadata,
            pricing=self.settings.model_pricing(),
        )
        self._trace_recorder.record(trace)

    def get_agent_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return [t.name for t in self._tools]

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
