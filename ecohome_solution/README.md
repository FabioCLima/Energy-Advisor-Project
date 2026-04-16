# EcoHome Energy Advisor

AI-powered energy optimization agent for smart homes with solar generation, dynamic pricing, and personalized energy-saving recommendations.

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
├── tests/                       ← pytest test suite
└── data/
    ├── documents/               ← RAG knowledge base
    ├── energy_data.db           ← SQLite (generated)
    └── vectorstore/             ← ChromaDB (generated)
```

## What The Solution Does

The Energy Advisor combines structured energy data, solar generation history, pricing information, weather context, and RAG-powered knowledge retrieval to answer optimization questions such as:

- when to charge an EV
- when to run appliances at lower cost
- how to use more self-generated solar energy
- how much money can be saved through schedule changes

## Main Capabilities

- Weather-aware energy planning
- Time-of-use pricing optimization
- Historical energy usage analysis
- Solar generation analysis
- RAG-based retrieval of energy-saving advice
- Savings estimation for suggested optimizations

## Setup

Install dependencies from inside `ecohome_solution/`:

```bash
cd ecohome_solution
pip install -r requirements.txt
```

Create a `.env` file in `ecohome_solution/` with the required credentials:

```bash
VOCAREUM_API_KEY=your_vocareum_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Model Switching (Fast vs. Quality)

This project supports easy switching between a cheaper "fast" model and a higher-quality model via environment variables:

```bash
# Choose preset: fast | quality | custom
ENERGY_ADVISOR_MODEL_PRESET=fast

# Defaults (override if you want)
ENERGY_ADVISOR_MODEL_FAST=gpt-5-mini
ENERGY_ADVISOR_MODEL_QUALITY=gpt-5.2

# If preset=custom, set the exact model name:
# ENERGY_ADVISOR_MODEL=...
```

If you are using a Vocareum proxy, set the base URL explicitly:

```bash
ENERGY_ADVISOR_BASE_URL=https://openai.vocareum.com/v1
```

## Run Order

Execute the notebooks in this order:

1. `01_db_setup.ipynb`
2. `02_rag_setup.ipynb`
3. `03_run_and_evaluate.ipynb`

These notebooks assume they are run from within the `ecohome_solution/` directory, where relative paths such as `data/...` resolve correctly.

## Key Files

- `energy_advisor/agent.py`: LangGraph ReAct agent wrapper
- `energy_advisor/tools/`: LangChain tools (weather, pricing, energy_data, rag, savings)
- `energy_advisor/services/database.py`: SQLAlchemy models and DB manager
- `energy_advisor/config.py`: Pydantic-settings v2 configuration
- `data/documents/`: knowledge base files for RAG
- `main.py`: CLI entrypoint (`python main.py "your question"`)

## Running from the CLI

```bash
cd ecohome_solution
python main.py "When should I charge my EV tonight?"
python main.py "How can I maximise solar self-consumption?" --context "5kW system, San Francisco"
```

## Running tests

```bash
cd ecohome_solution
pytest tests/ -v
```

## Dependencies

Runtime dependencies are in `requirements.txt`; development and test tools in `requirements-dev.txt`.

Install for development:

```bash
pip install -r requirements-dev.txt
```

Current documented local runtime: Python `3.12.3`

Notable runtime packages:

- `langchain>=0.3.0`
- `langchain-openai>=0.2.0`
- `langchain-community>=0.3.0`
- `langgraph>=0.2.0`
- `openai>=1.40.0`
- `sqlalchemy>=2.0.23`
- `chromadb>=0.5.0`
- `pydantic>=2.0.0`
- `pydantic-settings>=2.0.0`
- `loguru>=0.7.2`
- `python-dotenv>=1.0.0`

## Notes

- Generated database and vector store artifacts are ignored in Git, except for the `.gitkeep` placeholder in `data/vectorstore/`.
- The project brief and architecture notes are documented in [`../docs/project_overview.md`](../docs/project_overview.md).
