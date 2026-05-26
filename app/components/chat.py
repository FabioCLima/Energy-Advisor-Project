"""
Chat component for the EcoHome Energy Advisor.
Manages message history and agent invocation via Streamlit session state.
"""
from __future__ import annotations

import uuid

import streamlit as st
from langchain_core.runnables import RunnableConfig

_SUGGESTED_QUESTIONS = [
    "Quanto gastei com home office nos últimos 30 dias?",
    "Qual o melhor horário para carregar o Tesla esta noite?",
    "Qual dispositivo consome mais energia em casa?",
    "Quais são minhas maiores oportunidades de economia nos próximos 30 dias?",
]


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())


def _load_agent() -> object | None:
    if st.session_state.agent is not None:
        return st.session_state.agent
    try:
        from energy_advisor import EnergyAdvisorAgent
        st.session_state.agent = EnergyAdvisorAgent()
        return st.session_state.agent
    except Exception:
        return None


def _extract_tools_used(result: dict) -> list[str]:
    """Extract tool names from the LangGraph message history."""
    tools: list[str] = []
    for msg in result.get("messages", []):
        if hasattr(msg, "name") and msg.name and msg.name not in tools:
            tools.append(msg.name)
    return tools


def render_chat() -> None:
    _init_state()

    agent = _load_agent()
    if agent is None:
        st.warning(
            "Agent not initialized. Check that `OPENAI_API_KEY` is set in your `.env` file.",
            icon="🔑",
        )

    # Render message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("🔧 Tools used: " + " · ".join(f"`{t}`" for t in msg["tools"]))

    # Suggested questions — shown only on empty history
    if not st.session_state.messages:
        st.markdown("**Start with one of these questions:**")
        cols = st.columns(2)
        for i, q in enumerate(_SUGGESTED_QUESTIONS):
            if cols[i % 2].button(q, key=f"sugg_{i}", width="stretch"):
                st.session_state["_pending"] = q
                st.rerun()

    if "_pending" in st.session_state:
        _handle_question(st.session_state.pop("_pending"), agent)

    # User input
    if question := st.chat_input("Ask something about your energy usage..."):
        _handle_question(question, agent)


def _handle_question(question: str, agent: object | None) -> None:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if agent is None:
            answer = "Agent unavailable. Please set the API key and restart."
            tools: list[str] = []
            st.markdown(answer)
        else:
            try:
                # st.write_stream consumes the generator and renders tokens as they arrive.
                # Tool names accumulate in agent.last_tools_used as a side effect.
                answer = st.write_stream(
                    agent.stream(
                        question,
                        config=RunnableConfig(metadata={"session_id": st.session_state.session_id}),
                    )
                )
                tools = getattr(agent, "last_tools_used", [])
            except Exception as e:
                answer = f"❌ Agent error: {e}"
                tools = []
                st.markdown(answer)

        if tools:
            st.caption("🔧 Tools used: " + " · ".join(f"`{t}`" for t in tools))

    st.session_state.messages.append({"role": "assistant", "content": answer, "tools": tools})
