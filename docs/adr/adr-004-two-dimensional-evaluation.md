# ADR-004 — Two-dimensional evaluation: trajectory + LLM-as-judge

## Context
"The answer looks good" is not a metric. An agent can produce a plausible,
well-written answer without ever consulting data — the most dangerous failure
mode, because it reads exactly like a grounded one.

## Decision
Evaluate two independent dimensions per scenario
(`energy_advisor/evaluation/`):

1. **Trajectory** (deterministic): required tools must all be called
   (membership) and appear as an ordered subsequence of actual calls
   (order, when `order_matters=True`). Reported separately as
   `trajectory_pass` and `order_pass` so a reader knows *why* a run failed.
2. **LLM-as-judge** (rubric-scored 1–5): grounding, completeness,
   actionability, honesty — structured output validated by Pydantic.

The CI gate (`eval.yml`) runs trajectory-only: deterministic checks gate
builds; judge scores inform humans.

## Consequences
- Tool-bypass regressions are caught mechanically, even when the answer text
  still reads well.
- Judge limits, stated plainly: GPT-4o judging GPT-4o-mini shares training
  lineage (family bias), and scores are not calibrated against human ratings.
  That is why judge scores never gate the build.
- Every report carries `versions` (prompt hash, contract hash, git commit) —
  two eval runs are only comparable when they ran the same prompt.
