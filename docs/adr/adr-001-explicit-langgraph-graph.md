# ADR-001 — Explicit LangGraph graph instead of `create_react_agent`

## Context
LangGraph ships a prebuilt `create_react_agent` that would implement the same
reason → act → observe loop in one call. The project needs the agent's control
flow to be inspectable, testable and explainable in an interview setting.

## Decision
Build the graph explicitly: `AgentState` schema (messages only), an
`assistant` node, a `tools` node (`ToolNode`), a conditional edge routing on
the presence of `tool_calls`, and `tools → assistant` closing the loop
(`energy_advisor/agent.py`).

## Consequences
- Each piece is individually testable — `tests/test_agent.py` exercises
  routing, limits and traces with a scripted fake model and fake tools.
- Cross-cutting controls have an obvious attachment point: budget enforcement
  lives inside `assistant_node`; the iteration cap is a `recursion_limit` on
  the same graph.
- Cost: we own ~30 lines the prebuilt would give for free, and we must track
  LangGraph API evolution ourselves. Honest caveat: the topology is exactly
  standard ReAct — the value is auditability and the places we hook into it,
  not a novel graph.
