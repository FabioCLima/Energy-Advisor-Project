# ADR-002 — Aggregation inside tools: the LLM/data boundary

## Context
`query_energy_usage` could return raw hourly records (~2,000 rows for 30
days). LLMs summarizing large numeric tables hallucinate totals and invent
rows; token cost also scales linearly with payload size.

## Decision
Tools return pre-aggregated, business-shaped payloads (per-device totals,
~15 rows). The aggregation is SQL/pandas inside the service layer — never
delegated to the model via prompt instructions like "sum these rows".

## Consequences
- Grounding improves measurably: the judge's `grounding` criterion checks
  numbers are traceable to tool output, which only works when the tool output
  is small enough to be quoted faithfully.
- Token cost per request stays roughly constant regardless of date range.
- Cost: questions that genuinely need row-level granularity ("what was the
  exact peak hour?") need a dedicated tool or a finer aggregation — the
  boundary must be moved deliberately, not bypassed.

## Rule of thumb this encodes
Deterministic computation belongs in code; the LLM decides *what* to compute
and *how to explain it* — never executes the arithmetic itself.
