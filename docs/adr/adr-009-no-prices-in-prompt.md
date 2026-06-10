# ADR-009 — No tariff values in the system prompt

## Context
The system prompt embedded Enel SP tariffs (R$ 0.538 / 0.656 / 0.987 per kWh)
while simultaneously instructing the model "do not fabricate electricity
prices". Two sources of truth: the prompt's frozen numbers and the pricing
service's live, bandeira-aware values. ANEEL adjusts tariffs — the prompt
would diverge silently, and the model would answer from stale memory while
believing it was grounded.

## Decision
The prompt names the tariff *structure* (off-peak / mid-peak / peak windows —
stable domain knowledge) but never quotes R$/kWh values, and instructs:
"NEVER quote a tariff value from memory — always fetch current R$/kWh via
get_electricity_prices". The persona itself moved to a `UserProfile` object
(`energy_advisor/profile.py`) rendered into the prompt template — João is a
default, not hardcoded prose. `tests/test_prompts.py` enforces the absence of
price literals.

## Consequences
- One source of truth for prices; bandeira changes propagate automatically.
- Possible extra tool call per pricing question — that is the *intended*
  behavior, and the trajectory evaluation rewards it.
- Multi-user support became a profile-rendering question instead of a
  prompt-rewriting question.
- General rule this encodes: prompts hold *stable structure and policy*;
  *volatile facts* must come from tools at runtime.
