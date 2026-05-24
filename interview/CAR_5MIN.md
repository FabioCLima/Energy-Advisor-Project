# 5-Minute CAR Talk Track

## Context

Brazilian households with solar panels, EVs, and home offices face three disconnected data sources: energy bills with ANEEL tariff flags that change monthly, solar generation that depends on real-time irradiance, and usage patterns that span always-on loads, scheduled loads, and home-office devices.

Manually cross-referencing these to answer "what's the cheapest time to charge my car today?" is impossible without tooling. With Time-of-Use rates that range from R$ 0.538/kWh (off-peak) to R$ 0.987/kWh (peak), charging the EV at the wrong hour costs nearly 2× more — compounded over a year on a Tesla Model 3, that's ~R$ 900 in unnecessary spend.

I wanted something stronger than a notebook or single-model demo, so I treated this as a production-style ML + AI application and built it in three layers.

---

## Action

### 1. ML layer

- Built hourly usage forecasting with a **seasonal-naive baseline** and a `HistGradientBoostingRegressor` with lag features and cyclical hour/weekday encodings
- Added **hold-out evaluation** (last 7 days as test window) and persisted RMSE / MAE in the model artifact — the dashboard shows validation metrics instead of assuming ML is always better (for EV loads the baseline still wins on MAE)
- The optimizer crosses the 7-day forecast against the TOU tariff schedule to produce **ranked, quantified savings recommendations** in R$

### 2. AI application layer

- Wrapped the domain logic in a **LangGraph ReAct agent** with 9 specialized tools: consumption queries, solar generation, ANEEL pricing, weather (Open-Meteo), RAG knowledge base, savings calculator, usage forecaster, schedule optimizer, and recent summary
- The system prompt encodes João's full profile (Enel SP TOU rates, 4kWp panel, Tesla Model 3, home office Mon–Fri) so every answer is grounded in his specific data, not generic advice
- Added **two evaluation dimensions**: trajectory checks (the agent must call the right tools) and LLM-as-judge scoring on grounding, completeness, actionability, and honesty
- Implemented **provenance-aware fallback** for ANEEL pricing: in-memory cache → disk cache → live API fetch → bundled values, with the source exposed in the UI so the app never pretends data is fresher than it is

### 3. MLOps / deployment layer

- 87 tests, 87% core coverage, Ruff linting — all gated in CI
- **Reproducible bootstrap**: `ensure_demo_assets()` is idempotent; a fresh container provisions SQLite tables, João's 90-day sample dataset, and the forecasting artifacts on first boot with no manual steps
- **Single Docker image, two runtime modes**: `SERVICE_MODE=streamlit` serves the dashboard + chat; `SERVICE_MODE=api` exposes FastAPI + LangServe endpoints — same image, different entrypoint, easy to explain in production context
- CI publishes the image to **GitHub Container Registry** (`ghcr.io`) on every push to main; from there it can be pulled into AWS App Runner with a single environment variable

---

## Result

| Metric | Value |
| --- | --- |
| Tests passing | 87 |
| Core coverage | 87% |
| Trajectory pass rate | 12 / 12 (100%) |
| LLM-as-judge overall | 4.31 / 5.00 |
| Avg response time | ~10s (gpt-4o-mini, 9 tools) |
| Docker image | ghcr.io/fabiolima/energy-advisor-project:latest |
| Streamlit Cloud | public demo URL (live) |

Lowest-scoring agent scenarios and why:

- `current_tariff_period` (3.5/5) — correct rate, but limitations language was weak
- `predict_usage_tomorrow` (3.25/5) — forecast detail good, method explanation thin

Both are known, documented, and fixable — the point of the eval pipeline is that I can see them.

---

## Close

The main thing I learned was to treat AI as an **operable system**, not just a model.

The parts that mattered most were not the model choice or the prompt — they were evaluation (so I know when the agent is wrong), honest fallback behavior (so the app degrades gracefully when external data is unavailable), reproducible bootstrap (so any interviewer can run it in one command), and deployment surfaces that make the project easy to demo and easy to reason about in production.

If I were taking this to real users, the next layer would be multi-turn conversation memory, multi-household support (right now João is hardcoded), and a proper time-series database instead of SQLite.

---

## Anticipated questions and short answers

**"Why LangGraph instead of LCEL?"**
The ReAct loop — reason, call tool, observe, reason again — is not linear. LangGraph makes it an explicit state machine: each node is testable, each transition is auditable. When the agent fails, I see exactly which node, with which state.

**"Why is the EV model worse than baseline on MAE?"**
EV charging is sparse: João charges 3×/week. Lag features that work well for continuous loads see mostly zeros for EV, so the seasonal-naive baseline that knows "Sunday night = high probability" still wins on MAE. The solution is adding a binary "charging day" calendar feature — I documented it as a next step rather than hiding the metric.

**"How does it scale to multiple users?"**
Right now João is hardcoded — it's a demo. The path to multi-user is: `Settings` per session with a `user_id`, isolated SQLite per user (or Postgres with row-level scoping), and the system prompt as a template filled at session init. The agent graph itself is stateless and already thread-safe.

**"What would you do differently in production?"**
Replace SQLite with TimescaleDB, add streaming evaluation metrics to LangSmith (I have the tracer wired but no dashboards), replace ChromaDB with a managed vector store, and add rate limiting on the API layer. The CORS `allow_origins=["*"]` would get restricted to the known frontend origins.
