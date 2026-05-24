# MLOps, Observability, Drift and Guardrails Backlog

This backlog turns the educational EcoHome Energy Advisor into a product-oriented prototype.
The goal is to make the agent measurable, safer, cheaper to operate and easier to explain in a technical interview.

## Implementation Order

### 1. Local Agent Observability

**Why it matters:** A product agent needs traceability. It must be possible to answer what the user asked, which tools were used, how long the request took and whether the run succeeded.

**Scope:**
- Add structured local traces for agent invocations.
- Track request id, model, latency, tools used, success/error and response size.
- Keep the implementation dependency-light so it works locally, in Streamlit Cloud and in Docker.

**Acceptance criteria:**
- Agent invocations can produce structured trace files.
- Unit tests cover trace creation and metric aggregation.
- Existing agent behavior remains unchanged for users.

### 2. Cost and Latency Controls

**Why it matters:** LLM products are operational systems. Cost per request, latency and budget limits must be visible before the project can be discussed as production-aware.

**Scope:**
- Estimate LLM token cost from model pricing configuration.
- Record latency and approximate token usage.
- Add configurable warning thresholds for request latency and estimated cost.

**Acceptance criteria:**
- Evaluation reports include average latency and estimated cost fields.
- Cost estimator has deterministic unit tests.
- No network calls are introduced by this layer.

### 3. Evaluation Harness Quality Gates

**Why it matters:** The current harness validates tool trajectory. A stronger MLOps harness should also validate operational constraints such as errors, latency and cost.

**Scope:**
- Add optional quality gates to evaluation summary.
- Track scenarios above latency/cost thresholds.
- Keep LLM-as-judge optional.

**Acceptance criteria:**
- Evaluation JSON includes gate status.
- Quick evaluation can run with `--no-judge`.
- Existing scenario pass/fail output remains readable.

### 4. Drift Monitoring

**Why it matters:** Energy behavior changes over time. A product prototype should detect when recent consumption or forecast errors diverge from a baseline.

**Scope:**
- Add a lightweight drift monitor for tabular energy series.
- Compare baseline vs current windows for mean shift and error degradation.
- Generate JSON reports suitable for GitHub artifacts or future dashboards.

**Acceptance criteria:**
- Drift monitor works offline with pandas dataframes.
- Tests cover no-drift and drift cases.
- The design is compatible with future Evidently/MLflow integration.

### 5. Guardrails and Security

**Why it matters:** An AI assistant should not expose secrets, accept unsafe prompts blindly or invent operational numbers without evidence.

**Scope:**
- Add input guardrails for prompt injection and oversized requests.
- Add output guardrails for secret leakage patterns.
- Add evidence policy helpers for numeric energy/cost answers.

**Acceptance criteria:**
- Guardrail checks are deterministic and tested.
- Agent/API can reject unsafe input with a clear message.
- The rules are documented as product safety controls, not generic filters.

## Product Framing

These features should be presented as product-readiness layers:

1. The dashboard explains the user value.
2. The API exposes the product capability.
3. The agent coordinates tools and foundation model reasoning.
4. The harness verifies behavior.
5. Observability, drift and guardrails make the system operable.

