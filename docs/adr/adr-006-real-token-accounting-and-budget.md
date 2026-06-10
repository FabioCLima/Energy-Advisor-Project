# ADR-006 — Real token accounting and mid-run budget enforcement

## Context
The original cost estimate applied chars/4 to *question + final answer*. An
agent's cost lives elsewhere: the system prompt, tool payloads and every
intermediate ReAct iteration — typically the large majority of tokens. The
estimate understated cost by an order of magnitude, and the budget flag it
fed (`over_cost_budget`) never acted on anything.

## Decision
1. Sum provider `usage_metadata` across every `AIMessage` in the run
   (`extract_token_usage`); the chars/4 heuristic survives only as a fallback,
   and every trace declares which path was used (`cost_source`).
2. Enforce the budget mid-run: in `BLOCK` mode
   (`ENERGY_ADVISOR_BUDGET_MODE`), accumulated cost is checked after every LLM
   response inside `assistant_node`; crossing the limit raises
   `BudgetExceeded` (API → 429). `AUDIT` (default) keeps flag-only behavior.
3. Heuristic-only runs are never blocked — enforcement must not punish
   estimation error.

## Consequences
- Cost numbers in traces and eval reports are real, and their provenance is
  explicit — a dashboard can distinguish measured from estimated.
- The check happens at the only point a run can still be stopped before
  spending more (after each LLM response, before the next iteration).
- Latency stays flag-only by design: money not yet spent can be protected;
  time already elapsed cannot.
