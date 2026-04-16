---
tags: [ecohome, decisions, adr, architecture]
aliases: [Decisions, ADR, Design Decisions]
---

# Architectural Decisions

Key decisions made during the refactor and why they were made.

---

## ADR-01: Migrate `models/energy.py` into the package

**Decision:** Move `models/energy.py` → `energy_advisor/services/database.py`

**Context:** The tool `energy_data.py` used `from models.energy import DatabaseManager`. This is a "bare absolute import" — it only works if the current working directory contains a `models/` folder. If you run `python` from a different directory or install the package, it breaks silently.

**Consequence:** All database code now lives inside the `energy_advisor` package. The `models/` directory still exists as a backwards-compatibility shim that re-exports from the new location.

---

## ADR-02: Lazy `DatabaseManager` initialization with `lru_cache`

**Decision:** Use `functools.lru_cache` to lazily initialize `DatabaseManager` in tools

**Context:** The original code had `db_manager = DatabaseManager()` at module level. This means the database is connected the moment the module is imported — even during tests that don't need the database. It also hardcodes the path.

**Consequence:** The database is connected on first tool call, uses the `db_path` from `Settings`, and is cached for subsequent calls. Tests can override `db_path` via environment variables.

---

## ADR-03: Pydantic v2 migration

**Decision:** Migrate all Pydantic usage from v1 API to v2 API

**Context:** The `.venv` had Pydantic 2.13.1 installed, but all code used Pydantic v1 patterns (`BaseSettings` from `pydantic`, `parse_obj()`, `dict()`, `class Config:`). This caused silent validation failures.

**Key changes:**
- `BaseSettings` now from `pydantic_settings` (separate package)
- `model.dict()` → `model.model_dump()`
- `Model.parse_obj(data)` → `Model.model_validate(data)`
- `class Config:` → `model_config = SettingsConfigDict(...)`
- `Optional[str]` → `str | None` (Python 3.10+ union syntax)

---

## ADR-04: Split runtime vs dev dependencies

**Decision:** Create `requirements.txt` (runtime) + `requirements-dev.txt` (dev tools)

**Context:** The original single `requirements.txt` included pytest, jupyter, and ruff — tools only needed during development, not when running the agent. This makes production deploys heavier than necessary and conflates concerns.

**Convention:** `requirements-dev.txt` starts with `-r requirements.txt` so `pip install -r requirements-dev.txt` installs everything.

---

## ADR-05: `gpt-4o-mini` for fast, `gpt-4o` for quality

**Decision:** Replace invalid model names `gpt-5-mini` and `gpt-5.2` with real models

**Context:** The original config had model names that do not exist in the OpenAI API. This would cause the agent to fail immediately at startup.

**Choice:**
- `gpt-4o-mini` for the fast preset: excellent tool-calling capability at low cost; ideal for development iteration
- `gpt-4o` for the quality preset: best multi-step reasoning for complex energy queries that require 4+ tool calls

---

## ADR-06: Bootstrap as Python modules, not just notebooks

**Decision:** Implement `bootstrap/db_setup.py`, `bootstrap/sample_data.py`, `bootstrap/rag_setup.py` as runnable modules

**Context:** The original setup relied entirely on Jupyter notebooks for initialization. Notebooks cannot be run in CI/CD, deployment pipelines, or from the CLI without a browser.

**Consequence:** The system can now be bootstrapped with three terminal commands. Notebooks still exist but call the package code rather than reimplementing logic.

---

## ADR-07: RAG paths injected from Settings

**Decision:** The `search_energy_tips` tool reads `vectorstore_dir` and `documents_dir` from `Settings`

**Context:** The original tool had `persist_directory = "data/vectorstore"` hardcoded. This breaks when the working directory is not `ecohome_solution/` and makes testing impossible without a real vectorstore.

**Consequence:** Paths are configurable via environment variables and can be overridden in tests with `tmp_path` fixtures.

---

## ADR-08: `compute_savings` in service layer, not in tool

**Decision:** Extract savings math from `tools/savings.py` into `services/recommendations.py`

**Context:** The savings calculation (savings_kwh, savings_usd, annual_savings_usd) was inline in the tool. This made it untestable without invoking LangChain and prevented reuse in bootstrap scripts or notebooks.

**Consequence:** `services/recommendations.py` is tested directly with 7 unit tests. The tool becomes a thin wrapper: validate → call service → serialize.

## Related Notes

- [[01_Architecture]] — the layer model these decisions enforce
- [[09_Testing]] — how these decisions improve testability
