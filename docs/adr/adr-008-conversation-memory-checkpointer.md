# ADR-008 — Conversation memory via LangGraph checkpointer

## Context
The agent was single-turn: every request rebuilt the message list from
scratch, so follow-ups ("e no fim de semana?") lost all context. The natural
place for memory in LangGraph is the checkpointer — not prompt-stuffing
history by hand.

## Decision
The graph compiles with `MemorySaver`. The thread is keyed by the
`session_id` the API already accepts; requests without one get a fresh thread
per `request_id` (previous single-turn behavior, unchanged). The first turn
of a thread receives the full system context; follow-up turns send only the
new question — the checkpointer holds the history. Input guardrails run on
every turn.

## Consequences
- Multi-turn works across both `invoke` and `stream` for the same session.
- The distinction this encodes for juniors: **graph state** (what flows
  through one execution) vs **memory between executions** (what the
  checkpointer persists per thread) — two different problems LangGraph solves
  with two different mechanisms.
- Cost: `MemorySaver` is per-process RAM — threads never expire and don't
  survive restarts or multiple replicas. The documented evolution is a
  persistent checkpointer (`SqliteSaver`/`PostgresSaver`) plus thread TTL.
