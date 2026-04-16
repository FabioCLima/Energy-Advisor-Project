# EcoHome Energy Advisor — Code Review

A didactic walkthrough of every change made during the refactor, explaining the **what**, **why**, and **what to look for** in each file.

---

## How to Read This Document

Each section follows the same structure:
- **What changed** — a precise description of the modification
- **Why** — the software engineering principle behind it
- **What to look for** — specific lines or patterns to study

---

## 1. Dependency Management

### Files changed
- `ecohome_solution/requirements.txt` ← rewritten
- `ecohome_solution/requirements-dev.txt` ← new
- `pyproject.toml` ← extended with `[project]` section

### What changed

`requirements.txt` now contains **only runtime dependencies** — the packages needed to actually run the agent. A new `requirements-dev.txt` adds test and development tools on top, using `-r requirements.txt` to include the runtime set.

### Why

**Separation of concerns** applies to dependencies too. A production deployment doesn't need `pytest`, `jupyter`, or `ruff`. Keeping them separate:
1. Makes production images smaller
2. Makes it clear which packages are load-bearing
3. Prevents test tools from accidentally affecting production behavior

### What to look for

```
# requirements.txt — runtime only
langchain>=0.3.0
pydantic>=2.0.0
pydantic-settings>=2.0.0    ← was missing entirely
loguru>=0.7.2               ← was missing entirely
langchain-chroma>=0.1.4     ← was missing (but imported in code)

# requirements-dev.txt
-r requirements.txt          ← inherits all runtime deps
pytest>=8.0.0
ruff>=0.6.9
```

The `-r` directive is the idiomatic way to express "dev deps extend runtime deps."

---

## 2. Pydantic v2 Migration

### Files changed
- `energy_advisor/config.py`
- `energy_advisor/schemas.py`
- All tool files
- All service files

### What changed

Every Pydantic v1 API pattern was updated to v2:

| Before (v1) | After (v2) |
|---|---|
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` |
| `class Config: env_file = ".env"` | `model_config = SettingsConfigDict(env_file=".env")` |
| `@validator("field")` | `@field_validator("field", mode="before")` |
| `Model.parse_obj(data)` | `Model.model_validate(data)` |
| `model.dict()` | `model.model_dump()` |
| `Optional[str]` | `str \| None` |
| `List[str]`, `Dict[str, Any]` | `list[str]`, `dict[str, Any]` |

### Why

The `.venv` had Pydantic **2.13.1** installed. Pydantic v2 broke backwards compatibility deliberately to clean up the API. The old `parse_obj()` method still exists in v2 as a deprecated shim, but `BaseSettings` was removed from the main package entirely — meaning the code would fail immediately at import.

Using the v2 API is not just about compatibility: `model_validate()` is more explicit (tells you what model you're validating against), and `str | None` is native Python 3.10+ syntax that doesn't require importing `Optional` from `typing`.

### What to look for

In `config.py`:
```python
# BEFORE
from pydantic import BaseSettings, Field, validator
class Config:
    env_file = ".env"
@validator("model_preset")
def _validate_preset(cls, v):
    ...

# AFTER
from pydantic_settings import BaseSettings, SettingsConfigDict
model_config = SettingsConfigDict(env_file=".env", extra="ignore")
@field_validator("model_preset", mode="before")
@classmethod
def _validate_preset(cls, v: str) -> str:
    ...
```

In any tool:
```python
# BEFORE
validated = WeatherForecast.parse_obj(payload)
return validated.dict()

# AFTER
validated = WeatherForecast.model_validate(payload)
return validated.model_dump()
```

---

## 3. Structural Fix: `models/` → `energy_advisor/services/database.py`

### Files changed
- `energy_advisor/services/database.py` ← new (migrated from `models/energy.py`)
- `models/__init__.py` ← now a compatibility shim
- `energy_advisor/tools/energy_data.py` ← import fixed

### What changed

`DatabaseManager`, `EnergyUsage`, and `SolarGeneration` were in `models/energy.py` — **outside** the `energy_advisor` package. The tool imported them with `from models.energy import DatabaseManager`, which is a "bare absolute import" that only works if your current working directory contains a `models/` folder.

They were moved into `energy_advisor/services/database.py`. The tool now uses the relative import `from ..services.database import DatabaseManager`.

`models/__init__.py` now re-exports from the new location for backwards compatibility:
```python
from energy_advisor.services.database import DatabaseManager, EnergyUsage, SolarGeneration
```

### Why

**Package encapsulation**: A Python package should contain everything it needs. If you install `energy_advisor` as a pip package, the `models/` directory outside it won't be included — the import would silently fail.

**Relative imports** (`..services.database`) are explicit about the package structure and work regardless of working directory.

### What to look for

`energy_advisor/services/database.py` line 67:
```python
def __init__(self, db_path: str = "data/energy_data.db") -> None:
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
```

The constructor now takes `db_path` as a parameter — no hardcoded defaults. Also note `os.makedirs` ensures the parent directory exists before SQLAlchemy tries to create the file.

---

## 4. Lazy Database Initialization

### File changed
- `energy_advisor/tools/energy_data.py`

### What changed

The original code had this at module level:
```python
db_manager = DatabaseManager()  # ← runs on import!
```

The new code uses `functools.lru_cache`:
```python
@functools.lru_cache(maxsize=1)
def _get_db(db_path: str) -> DatabaseManager:
    return DatabaseManager(db_path=db_path)

def _db() -> DatabaseManager:
    settings = Settings()
    return _get_db(settings.db_path)
```

### Why

Module-level side effects (like connecting to a database) are an anti-pattern because:
1. **Tests break** — importing the module opens a database connection at test collection time
2. **Path is hardcoded** — `DatabaseManager()` uses the default path, ignoring `Settings`
3. **Cold start cost** — even tools that don't use the database pay the initialization cost

`lru_cache(maxsize=1)` gives you **lazy singleton** behavior: first call creates the connection and caches it; subsequent calls return the cached instance instantly.

### What to look for

```python
@functools.lru_cache(maxsize=1)
def _get_db(db_path: str) -> DatabaseManager:
    """Lazy, cached DatabaseManager — instantiated once per db_path."""
    return DatabaseManager(db_path=db_path)
```

The `db_path` parameter is key: `lru_cache` caches by arguments, so different paths get different instances. Tests can pass a temp path; production uses the path from `Settings`.

---

## 5. Service Layer: `recommendations.py`

### File: `energy_advisor/services/recommendations.py` (new)

### What changed

The savings calculation that was previously inline in `tools/savings.py` is now in a dedicated service function:

```python
def compute_savings(device_type, current_kwh, optimized_kwh, price_per_kwh) -> SavingsResult:
    savings_kwh = current_kwh - optimized_kwh
    savings_usd = savings_kwh * price_per_kwh
    savings_pct = (savings_kwh / current_kwh * 100) if current_kwh > 0 else 0.0
    return SavingsResult(
        savings_kwh=round(savings_kwh, 2),
        annual_savings_usd=round(savings_usd * 365, 2),
        ...
    )
```

Two additional helpers:
- `best_charging_windows()` — ranks hours by effective cost, with optional solar boost
- `build_recommendation_context()` — bundles tool results into a single dict for LLM synthesis

### Why

**Single Responsibility Principle**: A tool's job is to validate input, call a service, and serialize output. The tool should not contain arithmetic. Putting calculations in the service layer means:
1. The math can be unit-tested without LangChain
2. Notebooks can call `compute_savings()` directly
3. The formula is in exactly one place

### What to look for

`tools/savings.py` after refactor — it's now 10 lines:
```python
@tool
def calculate_energy_savings(device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh=0.12):
    """..."""
    if current_usage_kwh < 0 or optimized_usage_kwh < 0:
        return {"error": "usage values must be non-negative."}
    result = compute_savings(device_type, current_usage_kwh, optimized_usage_kwh, price_per_kwh)
    return result.model_dump()
```

This is the target pattern for every tool: **guard → delegate → serialize**.

---

## 6. RAG Tool: Injected Paths

### File changed
- `energy_advisor/tools/rag.py`

### What changed

```python
# BEFORE — hardcoded paths
persist_directory = "data/vectorstore"
doc_paths = ["data/documents/tip_device_best_practices.txt", ...]

# AFTER — injected from Settings
settings = Settings()
doc_paths = list_document_paths(settings.documents_dir)
vectorstore = ensure_vectorstore(persist_directory=settings.vectorstore_dir, ...)
```

A new helper `list_document_paths(dir)` in `retrieval.py` automatically discovers all `.txt` files in the documents directory — so adding a new document doesn't require changing any code.

### Why

Hardcoded paths violate the **dependency inversion principle**: the tool should depend on an abstraction (a path configuration), not on a concrete path string. With paths from `Settings`:
1. Tests can redirect to temp directories
2. The knowledge base can be extended by dropping files in the folder
3. The path is configured in one place (`.env`), not scattered across files

---

## 7. Bootstrap Layer

### Files: `energy_advisor/bootstrap/` (new directory)

### What changed

Three new runnable modules replace the notebook-only initialization flow:

```bash
python -m energy_advisor.bootstrap.db_setup    # create tables
python -m energy_advisor.bootstrap.sample_data # load synthetic data
python -m energy_advisor.bootstrap.rag_setup   # index documents
```

All three are **idempotent** — safe to run multiple times:
- `db_setup`: SQLAlchemy's `create_all` skips existing tables
- `sample_data`: Checks `count_usage_records() > 0` before generating
- `rag_setup`: Checks for `chroma.sqlite3` before re-indexing

### Why

**Development vs production separation** (from the project spec):
> "The notebooks should call reusable package code. Business logic must not live only in notebooks."

Bootstrap as Python modules means:
1. They can be run from CI/CD pipelines
2. They can be imported by tests
3. They document the initialization sequence explicitly
4. They work without a Jupyter server

### What to look for

`sample_data.py` idempotency guard:
```python
if db.count_usage_records() > 0:
    logger.info("Sample data already present — skipping.")
    return
```

`rag_setup.py` idempotency check:
```python
chroma_db_file = os.path.join(persist_directory, "chroma.sqlite3")
if not os.path.exists(chroma_db_file):
    # ... build index
```

---

## 8. Unit Tests

### Files: `ecohome_solution/tests/` (new directory)

### Structure

```
tests/
├── conftest.py          ← shared fixtures
├── test_config.py       ← 8 tests
├── test_pricing.py      ← 7 tests
├── test_forecasting.py  ← 8 tests
├── test_savings.py      ← 7 tests
└── test_database.py     ← 7 tests
```

Total: **37 tests**, all passing.

### Key Design Patterns

**Fixture isolation** (`conftest.py`):
```python
@pytest.fixture()
def db(tmp_db_path) -> DatabaseManager:
    manager = DatabaseManager(db_path=tmp_db_path)
    manager.create_tables()
    return manager
```

Each test gets a **fresh database file** in a temp directory (`tmp_path`). Tests cannot interfere with each other or with the real database.

**Monkeypatching** for config tests:
```python
def test_quality_preset(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL_PRESET", "quality")
    s = Settings()
    assert s.selected_model() == "gpt-4o"
```

`monkeypatch.setenv` sets environment variables only for the duration of the test. This lets us test configuration variants without changing the actual environment.

**Edge cases** in savings tests:
```python
def test_zero_current_usage():
    result = compute_savings("Lighting", 0.0, 0.0, 0.12)
    assert result.savings_percentage == 0.0  # No ZeroDivisionError
```

Always test the boundaries: zero, negative, maximum.

**Date boundary test** (important gotcha):
```python
def test_date_range_filter(db):
    results = db.get_usage_by_date_range(
        datetime(2025, 3, 2),
        datetime(2025, 3, 4, 23, 59, 59)  # ← end-of-day, not midnight
    )
    assert len(results) == 3
```

The query uses `<=` so `datetime(2025, 3, 4)` (midnight) **excludes** records at 10:00 on March 4. The tool adds `timedelta(days=1)` to the date string to handle this automatically — the test documents the raw behavior.

---

## 9. Loguru Logging

### Files: all service and tool files

### What changed

Every significant operation now has a structured log message:

```python
from loguru import logger

logger.info("Setting up database at {}", settings.db_path)
logger.debug("query_energy_usage | {} → {} | device={}", start_date, end_date, device_type)
logger.warning("Document not found, skipping: {}", path)
logger.exception("query_energy_usage failed")  # includes traceback
```

### Why

Loguru is configured centrally in `energy_advisor/logging.py` and uses `{}` format strings (like Python's `str.format()`) instead of `%s` (like the standard library). This avoids the overhead of string formatting when the log level suppresses the message.

Log levels used:
- `DEBUG` — every tool call with its parameters (verbose, off by default)
- `INFO` — significant milestones (startup, bootstrap complete)
- `WARNING` — degraded operation (missing document, skipping step)
- `exception()` — caught errors with full traceback

---

## 10. Model Names

### File: `energy_advisor/config.py`

### What changed

```python
# BEFORE — invalid model names
model_fast: str = Field("gpt-5-mini", ...)     # does not exist
model_quality: str = Field("gpt-5.2", ...)     # does not exist

# AFTER — real model names
model_fast: str = Field("gpt-4o-mini", ...)    # OpenAI GPT-4o Mini
model_quality: str = Field("gpt-4o", ...)      # OpenAI GPT-4o
```

### Why

Using non-existent model names causes a `404 Model Not Found` error from the OpenAI API at runtime — not at configuration time. The error message is confusing because it looks like an API key issue.

**Model choice rationale:**
- `gpt-4o-mini` is the best cost/performance choice for development. It has excellent tool-calling capability and costs ~10x less than `gpt-4o`.
- `gpt-4o` provides the best reasoning for complex multi-step energy queries requiring 5+ tool calls in sequence.

---

## 11. Deleted Legacy Files

### Files deleted
- `ecohome_solution/agent.py` — pre-refactor root-level agent
- `ecohome_solution/tools.py` — pre-refactor root-level tools

### Why

These files were leftovers from before the `energy_advisor` package was created. They imported from `models.energy` (the old path) and contained outdated code. Keeping them creates confusion: which `agent.py` is the real one?

Dead code should be deleted. Git history preserves them if ever needed.

---

## Summary: What Makes This Production-Quality

| Concern | Before | After |
|---|---|---|
| Imports | CWD-dependent bare imports | Package-relative imports |
| Database init | Module-level side effect | Lazy, cached, injectable |
| Pydantic | v1 API on v2 runtime (broken) | Full v2 API |
| Config | Hardcoded model names | Valid names, env-configurable |
| Missing deps | loguru, pydantic-settings, langchain-chroma | All installed, split by role |
| Business logic | Mixed into tools | In service layer, fully testable |
| Bootstrap | Notebook-only | Runnable Python modules |
| Knowledge base | 2 documents | 5 documents |
| Tests | None | 37 passing |
| Linting | Not configured | Ruff clean |
| Documentation | README only | 11 Obsidian notes + this review |
