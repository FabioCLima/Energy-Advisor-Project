# ADR-010 — Topicality enforcement in the AgentContract

## Context
`AgentContract` declared `scope` and `allowed_topics` but nothing checked
them — a question about stock picks passed every guardrail (not injection,
not PII) and reached the model. A contract without a check was the last
remnant of the "declared but not enforced" class this project's audit phase
existed to eliminate.

## Decision
`AgentContract.check_scope()`: a deterministic, accent-insensitive keyword
check (PT + EN energy domain), run **only on the first turn of a thread** —
follow-ups like "e no fim de semana?" carry no domain keyword by nature; the
conversation's scope was established on turn 1. Rollout reuses the house
AUDIT/BLOCK pattern (`ENERGY_ADVISOR_SCOPE_MODE`, default AUDIT): AUDIT logs
and flags the trace (`scope_check=out_of_scope`); BLOCK answers with a
friendly redirect **without invoking the LLM at all**. The keyword set lives
in the contract, so changing it changes the `contract_hash` in eval reports.

## Consequences
- Out-of-scope handling is now measurable (trace flag) before it is
  restrictive (BLOCK), and free when it blocks — no tokens spent.
- The eval harness tests the control itself: the out-of-scope adversarial
  scenario asserts `check_scope` flags it, deterministically, no LLM call.
- Cost, stated plainly: keyword matching can't grade nuance — greetings get
  flagged (harmless in AUDIT; friendly redirect in BLOCK), and an adversary
  can wrap any topic in energy words. This is product scope control, not a
  security boundary; the documented evolution is a lightweight classifier.
- Zero false positives on the 18 eval questions is enforced by a
  parametrized test — the keyword list cannot silently drift away from the
  product's own benchmark.
