---
tags: [ecohome, architecture, design]
aliases: [Architecture, System Design]
---

# Architecture

The system is organized into **six layers**. Each layer has a single responsibility and communicates only with the layers adjacent to it.

## Layer Stack

```
User Question
     │
     ▼
┌─────────────────────────────┐
│  Interaction Layer          │  CLI / Notebook / future API
├─────────────────────────────┤
│  Agent Orchestration        │  LangGraph ReAct (agent.py)
├─────────────────────────────┤
│  Tooling Layer              │  tools/ — thin, validated wrappers
├─────────────────────────────┤
│  Service Layer              │  services/ — pure business logic
├─────────────────────────────┤
│  Storage Layer              │  SQLite + ChromaDB
└─────────────────────────────┘
              │
              ▼
     Observability Layer
     (Loguru + LangSmith)
```

## End-to-End Runtime Flow

```mermaid
flowchart TD
    A[User Question] --> B[main.py / Notebook]
    B --> C[EnergyAdvisorAgent.invoke]
    C --> D[LangGraph ReAct Loop]
    D --> E[Weather Tool]
    D --> F[Pricing Tool]
    D --> G[Energy Data Tools]
    D --> H[RAG Search Tool]
    D --> I[Savings Tool]
    E & F --> J[services/forecasting + pricing]
    G --> K[(SQLite energy_data.db)]
    H --> L[(ChromaDB vectorstore)]
    I --> M[services/recommendations]
    J & K & L & M --> N[LLM synthesis]
    N --> O[Final Answer]
```

## Internal Decision Flow

```mermaid
flowchart TD
    A[Receive Question] --> B{Classify Intent}
    B -->|Historical data| C[query_energy_usage / query_solar_generation]
    B -->|Pricing| D[get_electricity_prices]
    B -->|Forecast| E[get_weather_forecast]
    B -->|Best practices| F[search_energy_tips]
    B -->|Savings calc| G[calculate_energy_savings]
    C & D & E & F & G --> H[Assemble Context]
    H --> I[LLM: Build Recommendation]
    I --> J[Response with assumptions]
```

## Development vs Production Flow

```mermaid
flowchart LR
    A[Bootstrap Scripts] --> B[SQLite + ChromaDB]
    B --> C[EnergyAdvisorAgent]
    C --> D[CLI main.py]
    C --> E[Notebooks 03]
    C --> F[future HTTP API]
```

## Key Design Principles

| Principle | How it's applied |
|---|---|
| Separation of concerns | Tools call services; services own logic; agent orchestrates |
| Validate at boundaries | Pydantic on every tool input and output |
| Injection over globals | `DatabaseManager(db_path)` from `Settings`, not hardcoded |
| Idempotent bootstrap | DB setup and RAG indexing are safe to re-run |
| No logic in notebooks | Notebooks import package code; cells contain no business rules |

## Related Notes

- [[02_Config_and_Settings]] — where settings flow into layers
- [[03_Agent_and_Prompts]] — how the agent orchestration layer works
- [[04_Tools]] — the tooling layer in detail
- [[05_Services]] — the service layer in detail
