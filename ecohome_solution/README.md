# EcoHome Energy Advisor

AI-powered energy optimization agent for smart homes with solar generation, dynamic pricing, and personalized energy-saving recommendations.

## Submission Layout

This project is organized to match the submission requirement that all deliverables live under `ecohome_solution/`.

```text
ecohome_solution/
├── 01_db_setup.ipynb
├── 02_rag_setup.ipynb
├── 03_run_and_evaluate.ipynb
├── agent.py
├── tools.py
├── requirements.txt
├── models/
│   ├── __init__.py
│   └── energy.py
└── data/
    ├── documents/
    │   ├── tip_device_best_practices.txt
    │   └── tip_energy_savings.txt
    ├── energy_data.db
    └── vectorstore/
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

## Run Order

Execute the notebooks in this order:

1. `01_db_setup.ipynb`
2. `02_rag_setup.ipynb`
3. `03_run_and_evaluate.ipynb`

These notebooks assume they are run from within the `ecohome_solution/` directory, where relative paths such as `data/...` and `models/...` resolve correctly.

## Key Files

- `agent.py`: LangGraph agent wrapper and model setup
- `tools.py`: tool definitions for weather, pricing, database access, RAG, and savings calculations
- `models/energy.py`: SQLAlchemy models and database manager
- `data/documents/`: knowledge base files for RAG

## Dependencies

Dependencies are listed in `requirements.txt`. Current documented local runtime:

- Python `3.12.3`

Notable packages and pinned versions:

- `langchain==0.1.0`
- `langchain-openai==0.0.5`
- `langchain-community==0.0.10`
- `langgraph==0.0.20`
- `sqlalchemy==2.0.23`
- `chromadb==0.4.18`
- `openai==1.3.0`
- `pandas==2.1.4`
- `numpy==1.24.3`
- `python-dotenv==1.0.0`
- `jupyter==1.0.0`
- `pytest==7.4.3`
- `requests==2.31.0`

## Notes

- Generated database and vector store artifacts are ignored in Git, except for the `.gitkeep` placeholder in `data/vectorstore/`.
- The project brief and architecture notes are documented in [`../docs/project_overview.md`](../docs/project_overview.md).
