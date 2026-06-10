# Architecture Decision Records

Each ADR captures one structural decision: the context that forced it, the
decision itself, and the consequences (including what it costs us). One page
maximum. A junior reading the codebase should be able to distinguish
"deliberate decision" from "it just ended up that way" by checking this index.

| ADR | Decision |
|---|---|
| [ADR-001](adr-001-explicit-langgraph-graph.md) | Explicit LangGraph graph instead of `create_react_agent` |
| [ADR-002](adr-002-aggregation-inside-tools.md) | Aggregation inside tools — the LLM/data boundary |
| [ADR-003](adr-003-deterministic-guardrails-audit-block.md) | Deterministic guardrails with AUDIT/BLOCK rollout |
| [ADR-004](adr-004-two-dimensional-evaluation.md) | Two-dimensional evaluation: trajectory + LLM-as-judge |
| [ADR-005](adr-005-sqlite-with-migration-path.md) | SQLite with an explicit migration path |
| [ADR-006](adr-006-real-token-accounting-and-budget.md) | Real token accounting and mid-run budget enforcement |
| [ADR-007](adr-007-streaming-under-same-controls.md) | Streaming under the same controls as invoke |
| [ADR-008](adr-008-conversation-memory-checkpointer.md) | Conversation memory via LangGraph checkpointer |
| [ADR-009](adr-009-no-prices-in-prompt.md) | No tariff values in the system prompt |
