# EcoHome Energy Advisor

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct_Agent-6B48FF?logo=chainlink&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white)
![Open-Meteo](https://img.shields.io/badge/Open--Meteo-Real_Weather-4CAF50?logo=cloudflarepages&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-253_passed-brightgreen?logo=pytest&logoColor=white)
![Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen?logo=pytest&logoColor=white)
![CI](https://github.com/FabioCLima/Energy-Advisor-Project/actions/workflows/ci.yml/badge.svg?branch=master)
![Docker](https://img.shields.io/badge/GHCR-ghcr.io%2Ffabiolima%2Fenergy--advisor-2496ED?logo=docker&logoColor=white)

> AI-powered energy advisor for Brazilian households. Ask in natural language: *"Should I charge my Tesla now or wait for solar generation?"* The agent reasons over real consumption data, live weather, and ANEEL energy rates to give a grounded, quantified answer.

![EcoHome Dashboard](assets/dashboard.png)

---

## Quick Start

```bash
git clone https://github.com/FabioCLima/Energy-Advisor-Project.git
cd Energy-Advisor-Project
echo "OPENAI_API_KEY=sk-..." > .env
docker compose up
```

Open **http://localhost:8501** — the container bootstraps the demo dataset and local forecast artifacts on first run.

**Or pull the pre-built image directly:**

```bash
docker pull ghcr.io/fabiolima/energy-advisor-project:latest
docker run -e OPENAI_API_KEY=sk-... -p 8501:8501 ghcr.io/fabiolima/energy-advisor-project:latest
```

> No Docker? See [manual setup](#manual-setup) below.
> The same image also runs as an API (`SERVICE_MODE=api`). Cloud deploy notes: [Streamlit Cloud](deploy/streamlit/README.md) · [AWS App Runner](deploy/aws/README.md)

---

## The Problem

Brazilian households with solar panels, EVs, and home offices face three disconnected data sources:

- **Energy bills** (kWh and BRL, with ANEEL bandeira surcharges that change monthly)
- **Solar generation** (depends on irradiance — weather changes everything)
- **Usage patterns** (EV charges at night, home office runs 9–18h, AC peaks in summer)

Manually cross-referencing these to answer "what's the cheapest time to charge my car today?" is impossible without tooling. EcoHome automates that reasoning.

All demo data is generated for a realistic São Paulo household (4kWp solar, Tesla Model 3, home office — 90 days, 6,631 usage records): see [Persona João](docs/PRODUCT_NOTES.md#persona-joão).

---

## What the Agent Does

The LangGraph ReAct agent coordinates **9 specialized tools** and reasons over multiple sources before responding:

| Tool | Data source | What it enables |
|---|---|---|
| `query_energy_usage` | SQLite (90 days, per-device) | "How much did my AC cost last week?" |
| `query_solar_generation` | SQLite (hourly generation) | "When did my panel produce the most?" |
| `get_electricity_prices` | ANEEL TOU + bandeira table | "What's the current energy rate?" |
| `get_weather_forecast` | **Open-Meteo API** (real data) | "Will solar generate enough this afternoon?" |
| `search_energy_tips` | ChromaDB RAG (5 documents) | "Best practices for EV charging?" |
| `calculate_energy_savings` | Savings math engine | "How much would I save shifting to off-peak?" |
| `get_recent_energy_summary` | SQLite aggregate | "What's been my recent energy usage?" |
| `predict_energy_usage` | SQLite + baseline/ML model artifact | "What will my usage look like tomorrow?" |
| `optimize_energy_schedule` | Forecast router + pricing + heuristics | "What should I shift to save over the next 30 days?" |

**Example exchange:**

> **User:** Vale a pena ligar o ar-condicionado agora?
>
> **Agent:** Agora (15h) você está em horário mid-peak (R$ 0,6560/kWh) com irradiância solar moderada de 197 W/m² — seu painel está gerando parcialmente. O custo real do AC é de ~R$ 0,35/h com o offset solar. Se esperar até as 18h, o pico sobe para R$ 0,987/kWh. **Recomendação: ligue agora, antes do horário de ponta.**

---

## Architecture

```mermaid
flowchart TD
    User(["👤 User\n(natural language)"])
    UI["🖥️ Streamlit UI\nDashboard · Chat"]
    Agent["🤖 EnergyAdvisorAgent\nLangGraph ReAct loop"]
    LLM["🧠 GPT-4o-mini\nReasoning & tool selection"]

    subgraph Tools["🔧 9 Specialised Tools"]
        T1["query_energy_usage"]
        T2["query_solar_generation"]
        T3["get_electricity_prices"]
        T4["get_weather_forecast"]
        T5["search_energy_tips"]
        T6["calculate_energy_savings"]
        T7["get_recent_energy_summary"]
        T8["predict_energy_usage"]
        T9["optimize_energy_schedule"]
    end

    subgraph Data["💾 Data Layer"]
        DB[("SQLite\n90 days · per-device")]
        VS[("ChromaDB\nRAG · 5 docs")]
        API["Open-Meteo API\nReal solar irradiance"]
        ANEEL["ANEEL Energy Rate Table\nBRL · TOU · Bandeiras"]
    end

    User -->|question| UI
    UI -->|invoke / stream| Agent
    Agent <-->|reason + act| LLM
    Agent -->|tool call| Tools
    T1 & T2 & T7 --> DB
    T5 --> VS
    T4 --> API
    T3 --> ANEEL
    T6 --> ANEEL
    T8 --> DB
    T9 --> ANEEL
    T9 --> DB
    Tools -->|observation| Agent
    Agent -->|final answer| UI
    UI -->|rendered response| User
```

Six-layer design — each layer testable and replaceable independently:

| Layer | Component | Role |
|---|---|---|
| 1. Interaction | Streamlit | Dashboard + streaming chat |
| 2. Orchestration | LangGraph ReAct | Reason → Act → Observe loop |
| 3. Tools | 9 `@tool` functions | Isolated, typed, directly testable |
| 4. Services | Business logic | database · pricing · forecasting · retrieval |
| 5. Storage | SQLite + ChromaDB | Time-series + vector embeddings |
| 6. Observability | Loguru + LangSmith | Structured logs + optional trace UI |

The agent operates on a minimal shared `AgentState` (the full message thread, including tool calls), making the graph's behavior inspectable at every step. The ReAct loop runs under an explicit iteration cap: when exceeded, the user receives an honest "couldn't finish" answer and the trace records `error=recursion_limit` instead of a stack trace.

**Key decisions:**

- **LangGraph over LCEL** — the ReAct loop is not linear. LangGraph represents it as an explicit state machine: each node independently testable, each transition auditable. When the agent fails, you see exactly which node, with which state.
- **SQLite over PostgreSQL** — portability for demo. `DatabaseManager` uses SQLAlchemy; swapping the connection string migrates to PostgreSQL with no application code changes.
- **Open-Meteo over synthetic weather** — free, no API key, provides `direct_radiation + diffuse_radiation` (W/m²) — the exact inputs for photovoltaic estimation. Falls back to deterministic synthetic data if unreachable.
- **ANEEL rate provenance** — rates resolve through a provenance-aware chain: in-memory cache → disk cache → external fetch → bundled fallback. The dashboard surfaces `source`, `fetched_at`, and `fallback_used`.
- **Aggregated tool output** — `query_energy_usage` returns per-device totals (~15 rows), not raw records (~2,000 rows). Raw records sent to an LLM produce hallucinated answers; aggregation happens inside the tool, not in the prompt.
- **No prices in the prompt** — the system prompt names tariff windows but never quotes R$/kWh; the model must call `get_electricity_prices`. A prompt that both forbids fabricating prices and contains prices diverges silently (guarded by `tests/test_prompts.py`).
- **Conversation memory via checkpointer** — requests carrying a `session_id` reuse a LangGraph thread (`MemorySaver`); follow-ups keep context, requests without one stay single-turn.

---

## Evaluation

The agent is evaluated across **18 scenarios in four categories** — because evaluating an agent is mostly evaluating how it fails, not just how it succeeds:

| Category | Scenarios | What it proves |
|---|---|---|
| `core` | 11 | Grounded answers on the happy path |
| `adversarial` | 3 | Out-of-scope flagged by the contract (no LLM call), PT-BR prompt injection blocked, and **honesty under tool failure** (empty DB → the answer must state the limitation, not fabricate numbers) |
| `multi_turn` | 2 | Follow-ups keep context through the session thread ("e no fim de semana?") |
| `rag` | 2 | Citations match a per-question gabarito and never reference files outside the corpus |

Each scenario defines the tools the agent must call, checked as **membership** (every required tool called) and **order** (required tools appear as an ordered subsequence of actual calls). Behavioral expectations (guardrail blocks, limitation statements, citation gabarito) are reported separately; a scenario passes only when both hold. An optional **LLM-as-judge** scores the final response on grounding, completeness, actionability, and honesty.

Latest local run (May 24, 2026):

| Mode | Result |
|---|---|
| Trajectory only | `12/12` scenarios passed · `0` errors · `8.93s` avg/scenario |
| LLM-as-judge | `4.31 / 5.00` overall — Grounding `4.33` · Completeness `4.42` · Actionability `4.00` · Honesty `4.50` |

```bash
python -m energy_advisor.evaluation.runner   # full suite; --quick / --no-judge available
```

Every report carries a `versions` block — SHA-256 of the system prompt and `AgentContract`, plus the git commit — so two entries in `eval_history.jsonl` are only compared when they ran the same prompt. Sample report: [`docs/examples/eval_report_sample.json`](docs/examples/eval_report_sample.json).

**CI gate** — [`eval.yml`](.github/workflows/eval.yml) runs the quick trajectory suite on PRs labelled `eval`, weekly, or on demand, and **fails the build** when `trajectory_pass_rate < 1.0` or any scenario errors.

---

## Production-Grade Controls

| Control | Implementation |
|---|---|
| Guardrails | Severity-tiered (low→critical): bilingual prompt-injection patterns, secret leakage, Brazilian PII/LGPD (CPF, CNPJ, phone, e-mail); scope enforcement via `AgentContract` with AUDIT/BLOCK modes — BLOCK redirects out-of-scope questions without spending tokens |
| Cost control | Real token counts from provider `usage_metadata` per ReAct iteration; budget enforcement (`ENERGY_ADVISOR_BUDGET_MODE=block` interrupts mid-run, API returns 429) |
| Observability | Local JSONL traces with rotation + trace reader (`python -m energy_advisor.observability.report`): cost/day, success rate, p95 latency, tool usage — also rendered live in the dashboard's **Operations tab**. Optional [LangSmith tracing](docs/PRODUCT_NOTES.md#observability-with-langsmith) |
| Drift monitoring | Weekly scheduled checks ([`drift.yml`](.github/workflows/drift.yml)): baseline vs current window, report artifact + warning annotation |
| API boundary | Opt-in auth (`X-API-Key`), per-IP rate limiting, CORS config, error hygiene (500s carry only a `request_id`; the exception goes to the log, correlated with the trace) |

![LangSmith tool observability](assets/langsmith_tools_observability.png)

**API:** `uv run uvicorn energy_advisor.api.app:app --reload --port 8000` → Swagger at `/docs`, endpoints `POST /advisor/invoke` and `POST /advisor/stream`.

---

## ML Model

The forecasting layer uses `HistGradientBoostingRegressor` over lagged hourly usage, rolling means, and cyclical hour / day-of-week features, trained on ~90 days of hourly history per device family. Artifacts ship with training window metadata and hold-out validation metrics.

| Forecast target | Model RMSE | Baseline RMSE | Model MAE | Baseline MAE | Takeaway |
|---|---|---|---|---|---|
| `all` | `0.8047` | `0.8420` | `0.4678` | `0.4322` | Better RMSE, worse MAE |
| `ev` | `0.4615` | `0.3458` | `0.1497` | `0.1170` | Baseline still wins |

The model forecasts recursively, so error accumulates with horizon — which is why the dashboard shows the selected method **and its saved validation metrics** before presenting the curve, instead of assuming the ML path is always better.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph 0.2 · LangChain 0.3 |
| LLM | OpenAI GPT-4o-mini (default) · GPT-4o (quality mode) |
| Weather | Open-Meteo API (free, no key required) |
| Database | SQLite + SQLAlchemy ORM |
| Vector store | ChromaDB (local, no external infra) |
| Validation | Pydantic v2 + Pydantic-settings |
| Dashboard | Streamlit + Plotly |
| Logging | Loguru (structured) + LangSmith (optional tracing) |
| Container | Docker + Docker Compose · single image with `streamlit` / `api` runtime modes |
| Tests | pytest · 253 tests · 81% coverage (incl. agent graph tests with injected fake model — no API key needed) |
| Linting | Ruff |

---

## Project Structure

```
Energy-Advisor-Project/
├── app/                          ← Streamlit UI (charts, chat, operations tab)
├── energy_advisor/
│   ├── agent.py                  ← LangGraph ReAct graph
│   ├── contract.py               ← AgentContract (scope, topics, enforcement)
│   ├── guardrails.py             ← Severity tiering, PII/LGPD, AUDIT/BLOCK
│   ├── observability.py          ← AgentTrace (session_id, tool args, costs)
│   ├── profile.py · prompts.py   ← UserProfile rendered into the system prompt
│   ├── tools/                    ← 9 @tool decorated functions
│   ├── evaluation/               ← Scenario harness, LLM-as-judge, eval history
│   ├── api/                      ← FastAPI service (invoke / stream)
│   └── services/                 ← database · pricing · forecasting · optimizer · RAG
├── tests/                        ← 253 unit tests (81% coverage)
├── data/                         ← RAG docs · SQLite · ChromaDB (generated)
├── migrations/                   ← Alembic schema migrations
├── deploy/                       ← AWS App Runner + Streamlit Cloud notes
└── Dockerfile · docker-compose.yml
```

---

## Manual Setup

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt

cp .env.example .env              # set OPENAI_API_KEY=sk-...

python -m energy_advisor.bootstrap.db_setup
python -m energy_advisor.bootstrap.sample_data
python -m energy_advisor.bootstrap.ml_train
python -m energy_advisor.bootstrap.rag_setup   # optional: needs embedding credentials

python -m streamlit run streamlit_app.py
pytest tests/ -v
```

---

## Documentation

| Document | What it is |
|---|---|
| [`docs/PRODUCT_NOTES.md`](docs/PRODUCT_NOTES.md) | Deployment surfaces, capability scope, LangSmith setup, persona and dashboard details |
| [`docs/adr/`](docs/adr/README.md) | Architecture Decision Records — one page per structural decision, with the cost of each |
| [`docs/ONBOARDING_JUNIOR_AI_ENGINEER.md`](docs/ONBOARDING_JUNIOR_AI_ENGINEER.md) | 5-day onboarding track for a junior contributor |
| [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md) | Module → AI-engineering concept mapping |
| [`docs/EXERCISES.md`](docs/EXERCISES.md) | 8 guided exercises extending the project |
| [`docs/mlops_implementation_notes.md`](docs/mlops_implementation_notes.md) | Observability and MLOps implementation rationale |
