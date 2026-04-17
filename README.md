<div align="center">

# EcoHome Energy Advisor

**AI agent for smart home energy optimization — RAG + multi-tool reasoning + solar/pricing intelligence**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct%20Agent-1C3C3C?style=flat)](https://langchain.com/langgraph)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?style=flat)](https://langchain.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat)](https://docs.pydantic.dev)
[![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen?style=flat&logo=pytest)](https://pytest.org)
[![License](https://img.shields.io/badge/license-MIT-success?style=flat)](LICENSE)

</div>

---

## What This Project Demonstrates

An autonomous AI agent that answers real energy optimization questions by combining five tools: live weather data, dynamic pricing windows, historical consumption patterns, solar generation forecasts, and a RAG knowledge base with curated energy-saving documents.

The agent reasons across all sources — not just retrieves from one — to give quantified, actionable recommendations.

**Example questions the agent handles:**
- *"When should I charge my EV tonight given current pricing?"*
- *"How can I maximize solar self-consumption tomorrow morning?"*
- *"How much would I save if I shifted my laundry to off-peak hours?"*

---

## Architecture

```
User Question
     │
     ▼
┌─────────────────────────────────┐
│    LangGraph ReAct Agent        │
│    (create_react_agent)         │
│                                 │
│  Reasons → Selects Tool → Acts  │
└────────────┬────────────────────┘
             │
   ┌─────────┼──────────────────────┐
   ▼         ▼          ▼     ▼     ▼
weather   pricing   energy   rag  savings
 tool      tool     data    tool   tool
             │          │     │
             ▼          ▼     ▼
         SQLite DB   SQLite  ChromaDB
         (pricing)  (usage)  (docs)
```

---

## Capabilities

| Capability | Description |
|---|---|
| Multi-tool reasoning | Combines weather, pricing, consumption, solar, and knowledge |
| Historical analysis | Personalized advice from stored usage patterns |
| RAG knowledge base | ChromaDB + 5 curated energy-saving document sets |
| Cost optimization | Dynamic pricing windows + solar forecasting |
| Savings estimation | Quantified reduction in kWh cost |

---

## Tech Stack

`Python 3.12` · `LangGraph` · `LangChain` · `Pydantic v2` · `ChromaDB` · `SQLAlchemy` · `SQLite` · `Loguru` · `pytest`

---

## Project Structure

```
ecohome_solution/
├── energy_advisor/
│   ├── agent.py          # LangGraph ReAct agent
│   ├── config.py         # Pydantic-settings config
│   ├── schemas.py        # Pydantic v2 I/O schemas
│   ├── prompts.py        # System prompt
│   ├── tools/            # 5 LangChain tools
│   │   ├── weather.py
│   │   ├── pricing.py
│   │   ├── energy_data.py
│   │   ├── rag.py
│   │   └── savings.py
│   └── services/         # Business logic layer
│       ├── database.py   # SQLAlchemy + DB manager
│       ├── forecasting.py
│       ├── pricing.py
│       ├── recommendations.py
│       └── retrieval.py
├── data/documents/       # RAG knowledge base (5 document sets)
├── tests/                # 37 unit tests
└── main.py               # CLI entrypoint
```

---

## Quickstart

```bash
git clone https://github.com/FabioCLima/Energy-Advisor-Project.git
cd Energy-Advisor-Project/ecohome_solution

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # set OPENAI_API_KEY

# Initialize data (first time only)
python -m energy_advisor.bootstrap.db_setup
python -m energy_advisor.bootstrap.sample_data
python -m energy_advisor.bootstrap.rag_setup

# Ask the agent
python main.py "When should I charge my EV tonight?"
python main.py "How can I maximise solar self-consumption?" --context "5kW system"
```

---

## Tests

```bash
pytest tests/ -v
# Expected: 37 passed
```

---

## Skills Demonstrated

`LangGraph ReAct agent` · `Multi-tool reasoning` · `RAG with ChromaDB` · `SQLAlchemy ORM` · `Pydantic v2 schemas` · `Service layer architecture` · `Structured logging` · `Test-driven development` · `Energy domain knowledge`
