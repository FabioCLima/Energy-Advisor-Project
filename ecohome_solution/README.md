# EcoHome Energy Advisor

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct_Agent-6B48FF?logo=chainlink&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=chainlink&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-37_passed-brightgreen?logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/Linter-Ruff-D7FF64?logo=ruff&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

AI-powered energy optimization agent for smart homes with solar generation, dynamic pricing, and personalized energy-saving recommendations.

---

## Submission Layout

This project is organized to match the submission requirement that all deliverables live under `ecohome_solution/`.

```text
ecohome_solution/
├── 01_db_setup.ipynb
├── 02_rag_setup.ipynb
├── 03_run_and_evaluate.ipynb
├── main.py                      ← CLI entrypoint
├── requirements.txt             ← runtime deps
├── requirements-dev.txt         ← dev/test deps
├── energy_advisor/              ← main Python package
│   ├── agent.py                 ← LangGraph ReAct agent
│   ├── config.py                ← Pydantic-settings config
│   ├── schemas.py               ← Pydantic v2 schemas
│   ├── prompts.py               ← system prompt
│   ├── logging.py               ← loguru setup
│   ├── tools/                   ← LangChain tools
│   │   ├── weather.py
│   │   ├── pricing.py
│   │   ├── energy_data.py
│   │   ├── rag.py
│   │   └── savings.py
│   ├── services/                ← business logic
│   │   ├── database.py          ← SQLAlchemy models + DB manager
│   │   ├── forecasting.py
│   │   ├── pricing.py
│   │   ├── recommendations.py
│   │   └── retrieval.py
│   └── bootstrap/               ← one-time setup scripts
│       ├── db_setup.py
│       ├── sample_data.py
│       └── rag_setup.py
├── tests/                       ← pytest test suite (37 tests)
└── data/
    ├── documents/               ← RAG knowledge base
    ├── energy_data.db           ← SQLite (generated)
    └── vectorstore/             ← ChromaDB (generated)
```

---

## What The Solution Does

The Energy Advisor combines structured energy data, solar generation history, pricing information, weather context, and RAG-powered knowledge retrieval to answer optimization questions such as:

- when to charge an EV
- when to run appliances at lower cost
- how to use more self-generated solar energy
- how much money can be saved through schedule changes

## Main Capabilities

| Capability | Description |
|---|---|
| Multi-tool reasoning | Weather, pricing, energy usage, solar generation |
| Historical analysis | Personalized recommendations from past behavior |
| RAG knowledge retrieval | Best practices from curated energy-saving documents |
| Cost optimization | Pricing windows + forecasted solar + device flexibility |
| Savings estimation | Quantified cost reduction and efficiency gains |

---

## Setup

### 1. Clone and enter the submission folder

```bash
git clone https://github.com/FabioCLima/Energy-Advisor-Project.git
cd Energy-Advisor-Project/ecohome_solution
```

### 2. Install dependencies

```bash
# Runtime only
pip install -r requirements.txt

# Development + tests (recommended)
pip install -r requirements-dev.txt
```

### 3. Configure environment

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

Minimum required variables in `.env`:

```bash
OPENAI_API_KEY=sk-...

# Optional: Vocareum proxy
VOCAREUM_API_KEY=...
ENERGY_ADVISOR_BASE_URL=https://openai.vocareum.com/v1

# Optional: LangSmith tracing
LANGCHAIN_API_KEY=...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=energy-advisor
```

### 4. Model switching

```bash
# fast (default) → gpt-4o-mini
ENERGY_ADVISOR_MODEL_PRESET=fast

# quality → gpt-4o
ENERGY_ADVISOR_MODEL_PRESET=quality

# custom → any model name
ENERGY_ADVISOR_MODEL_PRESET=custom
ENERGY_ADVISOR_MODEL=gpt-4-turbo
```

---

## Run Order

> All notebooks must be run from within `ecohome_solution/`.

| Step | Notebook | What it does |
|---|---|---|
| 1 | `01_db_setup.ipynb` | Creates SQLite DB and loads sample energy data |
| 2 | `02_rag_setup.ipynb` | Indexes knowledge-base documents into ChromaDB |
| 3 | `03_run_and_evaluate.ipynb` | Runs the agent against test scenarios and evaluates results |

**Alternative — run bootstrap as scripts:**

```bash
python -m energy_advisor.bootstrap.db_setup
python -m energy_advisor.bootstrap.sample_data
python -m energy_advisor.bootstrap.rag_setup
```

---

## Running from the CLI

```bash
cd ecohome_solution
python main.py "When should I charge my EV tonight?"
python main.py "How can I maximise solar self-consumption?" --context "5kW system, San Francisco"
```

---

## Running Tests

```bash
cd ecohome_solution
pytest tests/ -v
# Expected: 37 passed
```

---

## Key Files

| File | Role |
|---|---|
| `energy_advisor/agent.py` | LangGraph `create_react_agent` wrapper |
| `energy_advisor/config.py` | Pydantic-settings v2 — all runtime config |
| `energy_advisor/schemas.py` | Pydantic v2 input/output schemas |
| `energy_advisor/tools/` | Five LangChain tools: weather, pricing, energy_data, rag, savings |
| `energy_advisor/services/database.py` | SQLAlchemy models and DB manager |
| `energy_advisor/bootstrap/` | One-time DB + RAG setup scripts |
| `main.py` | CLI entrypoint |
| `tests/` | 37 unit tests across 5 test files |

---

## Dependencies

Runtime deps in `requirements.txt`, dev/test in `requirements-dev.txt`.

| Package | Version | Purpose |
|---|---|---|
| `langchain` | `>=0.3.0` | Core LLM framework |
| `langchain-openai` | `>=0.2.0` | OpenAI integration |
| `langgraph` | `>=0.2.0` | ReAct agent graph |
| `openai` | `>=1.40.0` | OpenAI client |
| `sqlalchemy` | `>=2.0.23` | ORM / SQLite |
| `chromadb` | `>=0.5.0` | Vector store |
| `pydantic` | `>=2.0.0` | Data validation |
| `pydantic-settings` | `>=2.0.0` | Env-based config |
| `loguru` | `>=0.7.2` | Structured logging |

---

## Notes

- Generated artifacts (`energy_data.db`, `vectorstore/`) are git-ignored; only `.gitkeep` is tracked.
- Architecture decisions and code walkthrough: [`../docs/CODE_REVIEW.md`](../docs/CODE_REVIEW.md)
- Full project brief: [`../docs/project_overview.md`](../docs/project_overview.md)
- Obsidian architecture notes: [`../docs/obsidian/`](../docs/obsidian/)
