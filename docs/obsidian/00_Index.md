---
tags: [ecohome, index, overview]
aliases: [Home, Start Here]
---

# EcoHome Energy Advisor — Project Index

An AI-powered smart-home energy optimization agent built with LangGraph, LangChain, SQLite, and ChromaDB.

## Quick Start

```bash
# 1. Install dependencies
pip install -r ecohome_solution/requirements-dev.txt

# 2. Add API key to .env
echo "OPENAI_API_KEY=sk-..." > ecohome_solution/.env

# 3. Bootstrap
cd ecohome_solution
python -m energy_advisor.bootstrap.db_setup
python -m energy_advisor.bootstrap.sample_data
python -m energy_advisor.bootstrap.rag_setup

# 4. Ask a question
python main.py "When should I charge my EV tonight?"
```

## Notes Map

| Note | What it covers |
|---|---|
| [[01_Architecture]] | System layers, data flow, Mermaid diagrams |
| [[02_Config_and_Settings]] | Environment variables, model presets, `.env` |
| [[03_Agent_and_Prompts]] | LangGraph ReAct loop, system prompt design |
| [[04_Tools]] | Each tool: inputs, outputs, examples |
| [[05_Services]] | Business logic layer — forecasting, pricing, recommendations |
| [[06_Data_Layer]] | SQLite models, DatabaseManager, query patterns |
| [[07_RAG_Pipeline]] | Document ingestion, ChromaDB, semantic search |
| [[08_Bootstrap]] | How to initialise the system from scratch |
| [[09_Testing]] | Test structure, fixtures, how to run |
| [[10_Decisions]] | Key architectural decisions and rationale |

## Project Root Structure

```
Energy-Advisor-Project/
├── ecohome_solution/          ← All deliverable code lives here
│   ├── energy_advisor/        ← The Python package
│   │   ├── bootstrap/         ← Initialisation scripts
│   │   ├── services/          ← Business logic
│   │   ├── tools/             ← LangChain tool wrappers
│   │   ├── agent.py           ← Agent orchestration
│   │   ├── config.py          ← Pydantic settings
│   │   ├── schemas.py         ← Data contracts
│   │   ├── prompts.py         ← System instructions
│   │   └── logging.py         ← Loguru configuration
│   ├── tests/                 ← Unit tests
│   ├── data/
│   │   ├── documents/         ← RAG knowledge base (.txt)
│   │   └── vectorstore/       ← ChromaDB (auto-created)
│   ├── main.py                ← CLI entrypoint
│   ├── requirements.txt       ← Runtime deps
│   └── requirements-dev.txt   ← Dev/test deps
└── docs/
    └── obsidian/              ← This vault
```
