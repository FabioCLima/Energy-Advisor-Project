# ADR-003 — Deterministic guardrails with AUDIT/BLOCK rollout

## Context
The agent faces three content risks: prompt injection on input, secret
leakage and PII reproduction (LGPD: CPF, CNPJ, phone, e-mail) on output.
LLM-based detection adds latency, cost and a non-deterministic dependency to
every request.

## Decision
Regex-based checks (`energy_advisor/guardrails.py`), severity-tiered
(LOW→CRITICAL), bilingual (EN + PT-BR), with a two-mode enforcement policy:
`AUDIT` logs and continues; `BLOCK` raises `GuardrailViolation`. PII on
*input* is audited, never blocked — users may legitimately reference their own
data; PII reproduced in *output* is blocked.

## Consequences
- Zero latency/cost, fully unit-testable (parametrized PT/EN suites), always on.
- The AUDIT mode enables observe-first rollout of any new rule — measure false
  positives in logs before flipping to BLOCK. The same pattern was later
  reused for budget enforcement (ADR-006), which is the point: enforcement
  policy is a reusable shape, not a one-off.
- Cost, stated plainly: regex catches known phrasings, not intent. Paraphrase,
  encoding tricks or a third language slip through. This is the *first* layer
  (with scope-limited prompt, tool whitelist and output checks behind it), and
  the documented evolution is a dedicated classifier or moderation endpoint.
