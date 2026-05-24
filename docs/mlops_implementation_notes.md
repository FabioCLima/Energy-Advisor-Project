# MLOps Implementation Notes

This document explains why the new MLOps features make sense for the EcoHome Energy Advisor prototype.
The project started as an educational AI agent/dashboard. These additions move it toward a product prototype that can be shown in GitHub, Streamlit Cloud and AWS conversations.

## 1. Local Agent Observability

### What was implemented

The project now has a local observability module that records structured JSONL traces for agent invocations.
Each trace can include:

- request id
- selected model
- question and answer size
- latency
- tools used
- success/error state
- estimated input/output tokens
- estimated cost
- cost and latency budget flags
- metadata passed by API clients

### Why this feature makes sense

A product-grade agent must be explainable operationally. It is not enough to know that the answer looked good. The engineering team needs to know which tools were used, how long the run took, whether the request failed and roughly how much the LLM call cost.

This also supports the interview narrative: the project now demonstrates awareness of production concerns without requiring a paid observability vendor to run locally.

## 2. Cost and Latency Quality Gates

### What was implemented

The evaluation harness now reports estimated cost and latency quality gates in addition to tool trajectory and optional LLM-as-judge scores.

The evaluation summary includes:

- total estimated cost
- average estimated cost
- latency budget violations
- cost budget violations
- overall quality gate status

### Why this feature makes sense

For MLOps and AI Engineering, model quality is only one part of the system. A useful agent also needs to operate within cost and latency constraints. This lets the project show that evaluation is tied to product constraints, not just answer quality.

In an interview, this is a strong distinction: the harness evaluates behavior, budget and reliability together.

## 3. Energy Drift Monitoring

### What was implemented

The project now includes a lightweight drift monitor for tabular energy data. It compares a baseline window against a current window and can flag:

- feature mean shift, such as higher recent kWh consumption
- forecast error degradation, using MAE change

The implementation is dataframe-based, so it can be fed from SQLite, CSV, notebooks, scheduled jobs or future cloud pipelines.

### Why this feature makes sense

Energy behavior changes over time. A user can buy a new appliance, change working hours, install solar panels or start charging an EV. If the forecast model keeps using old behavior assumptions, recommendations become less reliable.

This feature gives the project a practical monitoring story: detect when the data or forecast quality has moved enough to require review, retraining or investigation.

## 4. Guardrails and Security

### What was implemented

The project now has deterministic guardrails for:

- empty requests
- oversized requests
- prompt injection attempts
- secret or credential leakage in model output

The API now maps guardrail violations to HTTP 400 instead of treating them as internal server errors.

### Why this feature makes sense

An agent that can call tools and reason over user data needs basic safety boundaries. These rules are intentionally simple, deterministic and testable. They do not replace a full security program, but they demonstrate product thinking: unsafe requests should be rejected clearly, and credentials should never be returned in an assistant response.

## How this fits the product architecture

The new layers fit the system in process order:

1. User asks a question in Streamlit or the API.
2. Guardrails validate the request before the LLM is called.
3. The LangGraph agent decides whether to answer directly or call tools.
4. Tools retrieve energy, tariff, solar, forecast or recommendation data.
5. The foundation model synthesizes the final response.
6. Output guardrails check for sensitive leakage.
7. Observability records latency, tools, success, tokens and estimated cost.
8. The evaluation harness verifies trajectory, quality gates and optional judge scores.
9. Drift monitoring can run offline to detect when data behavior or forecast error changes.

## What should be studied next

The next professional step is to connect these local controls to managed infrastructure:

- LangSmith or OpenTelemetry for distributed LLM traces
- MLflow model registry for forecast model versions
- Evidently or custom scheduled jobs for drift reports
- AWS CloudWatch for logs and alarms
- AWS Secrets Manager for production secrets
- CI/CD quality gates that fail builds when tests, cost budgets or evaluation thresholds fail

The current implementation is intentionally lightweight. That is appropriate for a portfolio prototype: it works locally, keeps the code understandable and leaves a clear path to cloud-grade MLOps.
