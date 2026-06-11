# Product Notes

Design rationale and product-level details that complement the [README](../README.md).

## Deployment Surfaces

This project is intentionally packaged for two complementary deployment surfaces:

| Surface | Purpose | What it demonstrates |
|---|---|---|
| Streamlit Cloud | Public demo URL for the dashboard + chat | Product thinking and fast iteration |
| AWS App Runner | Production-style container deployment | Cloud, container, env-var, and bootstrap discipline |

The same codebase provisions demo assets on first boot: SQLite tables, sample data, and local forecasting artifacts. The container supports **two runtime modes** through environment variables:

- `SERVICE_MODE=streamlit`
- `SERVICE_MODE=api`

That keeps a clean progression from demo surface to cloud-native service without overcomplicating the architecture.

## Scope: prototype with production-grade controls

This repository is a **deliberate product prototype** — scoped to demonstrate the essential building blocks of an AI/ML product in the smallest credible scope: a usable dashboard, an API, a tool-using agent, model evaluation, observability, drift checks, guardrails, tests, Docker packaging and cloud deployment paths.

| Capability | Standalone implementation in this repo | Production-scale evolution |
|---|---|---|
| Product surface | Streamlit dashboard + chat | Dedicated frontend, auth, user accounts |
| Agent service | FastAPI + LangGraph ReAct agent | Multi-tenant API, rate limits, service mesh |
| Model/agent evaluation | 18 scenarios in 4 categories (core, **adversarial**, multi-turn, RAG-gabarito) with ordered tool-trajectory + behavioral checks, optional LLM-as-judge, CI eval gate (`eval.yml`), reports versioned by prompt/contract hash + git commit | Larger benchmark sets, human review workflows |
| Observability | Local JSONL traces (both `invoke` and `stream` paths) with size-based rotation, plus a trace reader — `python -m energy_advisor.observability.report` aggregates cost/day, success rate, p95 latency, budget flags and top tools | LangSmith/OpenTelemetry traces, Prometheus/Grafana, CloudWatch alarms |
| Cost control | Real token counts from provider `usage_metadata` (covering every ReAct iteration), with labelled chars/4 heuristic fallback (`cost_source` field); budget enforcement with AUDIT/BLOCK rollout (`ENERGY_ADVISOR_BUDGET_MODE` — BLOCK interrupts the loop mid-run, API returns 429) | Model routing, cache policy, org-level cost dashboards |
| Drift monitoring | Baseline vs current window checks run as a **weekly scheduled process** (`drift.yml`: report artifact + warning annotation, never a build failure) and on demand via `python -m energy_advisor.services.drift_report` | Evidently/MLflow jobs, retraining triggers, model registry governance |
| Guardrails | Severity-tiered checks (low→critical): bilingual (EN + PT-BR) prompt-injection patterns, secret leakage, Brazilian PII/LGPD (CPF, CNPJ, phone, e-mail); contract **topicality enforcement** (`ENERGY_ADVISOR_SCOPE_MODE`: AUDIT flags out-of-scope questions, BLOCK redirects without spending tokens); output validation applied to **both** `invoke` and token streaming | Classifier/moderation-based detection, policy engine, red-team suites |
| Deployment | Docker, Streamlit Cloud path, AWS App Runner path | IaC, blue/green deploys, autoscaling, secrets manager, VPC controls |

The project sits deliberately at the intersection of two roles:

- **ML Engineering:** forecasting model, validation metrics, drift monitoring, model artifacts, evaluation harness and deployment discipline.
- **AI Engineering:** LangGraph agent, tool calling, RAG-style retrieval, prompt/system design, LLM observability, guardrails and cost/latency control.

## Observability with LangSmith

LangSmith is used for production debugging and evaluation review — the agent supports LangChain/LangGraph tracing environment variables, and when enabled, the evaluation harness captures traces automatically. To enable:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls__...
export LANGCHAIN_PROJECT=ecohome-energy-advisor
```

Then run either the API or evaluation harness. In LangSmith, inspect:

- tool-call sequence per request
- LLM latency and token usage
- failed runs and exceptions
- prompt, model and response versions
- scenario traces from the evaluation harness
- regressions when changing prompts, tools or models

Local JSONL traces prove the concept and work anywhere; LangSmith adds a visual trace UI for debugging, demos and team review. For implementation rationale, see [`mlops_implementation_notes.md`](mlops_implementation_notes.md).

## Persona: João

João is the **default `UserProfile`** (`energy_advisor/profile.py`), rendered into the system prompt by `render_instructions()` — supporting another household means defining another profile, not rewriting the prompt. All sample data is generated for a realistic Brazilian household:

| Attribute | Value |
|---|---|
| Name | João — Python Developer |
| Location | São Paulo, SP |
| Work | Home office Mon–Fri |
| Solar | 4kWp panel (10 × 400W modules) |
| EV | Tesla Model 3 Long Range |
| Distributor | Enel SP |
| Data | 90 days · 6,631 usage records · 1,081 solar records |

Device profiles use `prob_fn: Callable[[datetime], float]` encoding domain knowledge: the Tesla charges stochastically on Tue/Thu/Sun nights (0h–5h, off-peak); the AC has 85% usage probability in January (SP summer) and 20% in May; solar follows a Gaussian curve peaking at noon scaled by monthly irradiance.

## Dashboard Charts

| Chart | What it shows |
|---|---|
| Consumption by Device | Per-device kWh + % of total; EV shown separately |
| Solar vs Consumption | Hourly average kW; green area = surplus exported to grid |
| Enel SP Energy Rates | TOU rates by hour; vertical line = current time |
| Home Office Cost | PC + Monitor + AC office; monthly and annual projections |

The "Insight of the Day" card (top of dashboard) combines the current energy rate period, real-time irradiance from Open-Meteo, and the cheapest upcoming window — all pre-computed, no agent call required.

### Operations tab

The **🔧 Operations** tab renders the agent's own telemetry from the local JSONL traces — the same aggregation as `python -m energy_advisor.observability.report`: requests and cost per day, success rate, avg/p95 latency, budget flags, out-of-scope count, cost provenance (`usage_metadata` vs heuristic), error breakdown, tool usage, and a raw drill-down of the last 20 traces. Every question asked in the chat tab shows up here seconds later.

## Evaluation details

Lowest-scoring scenarios from the latest judged run (May 24, 2026):

- `current_tariff_period` (`3.5/5`) — answer needs clearer source/limitations language.
- `recent_summary_24h` (`3.25/5`) — grounded but not actionable enough.
- `predict_usage_tomorrow` (`3.25/5`) — forecast is detailed, but recommendation/method explanation can be stronger.

Runner flags:

```bash
python -m energy_advisor.evaluation.runner
# Output: eval_report_YYYYMMDD_HHMMSS.json (timestamped by default)
# Summary appended to data/observability/eval_history.jsonl after each run
# --output path/to/report.json  override the output path
# --quick                       run 4 scenarios instead of all 12
# --no-judge                    skip LLM scoring (trajectory only)
```
