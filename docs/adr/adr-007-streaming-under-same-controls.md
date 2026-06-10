# ADR-007 — Streaming under the same controls as invoke

## Context
`invoke()` validated model output and recorded a trace; `stream()` — the path
the chat UI and the SSE endpoint actually use — yielded tokens with no output
guardrail and no observability. Security that depends on which method the
caller picked is not security.

## Decision
`stream()` runs under the same controls (`energy_advisor/agent.py`):

- **Guardrails**: the accumulated output is validated on every chunk
  (regex is cheap). First violating chunk stops the stream (`BLOCK`) or logs
  once (`AUDIT`).
- **Traces**: the graph streams with `stream_mode=["messages", "values"]`;
  the final `values` state gives the same complete message history `invoke()`
  has, so one identical `AgentTrace` is recorded per stream.
- **Limits**: same `recursion_limit`; on cap, the stream yields the honest
  fallback answer instead of dying mid-sentence.

## Consequences
- No execution path escapes output validation, cost accounting or tracing —
  this was the project's most serious integrity gap.
- Trade-off stated honestly: streaming has no "final answer" to check before
  sending, so earlier chunks may already have reached the client when a
  violation is detected. We stop the leak at the first violating chunk; the
  alternative (buffer everything, validate, then flush) would forfeit
  streaming's purpose.
