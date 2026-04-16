---
tags: [ecohome, services, business-logic]
aliases: [Services, Business Logic]
---

# Services

Services contain **pure business logic** with no LangChain decorators, no agent state, and no framework coupling. They are easy to unit-test, reuse, and swap.

## Why a Separate Service Layer?

Without a service layer, business logic accumulates in tools. Tools then become hard to test (because they require a full LangChain context) and hard to reuse (because the same calculation can't be called from a bootstrap script or a notebook).

```
Without services:          With services:
tool → logic               tool → service → logic
hard to test               easy to test
duplicated in notebooks    reusable everywhere
```

## Services Inventory

### `services/forecasting.py`

**Function:** `generate_hourly_forecast(location, days) → dict`

Generates a **deterministic** synthetic weather forecast. Given the same location and date, it always produces the same values — which makes tests reproducible.

**Algorithm:**
- SHA-256 hash of `location|date` → random seed
- Diurnal temperature curve (minimum at 03:00, maximum at 15:00)
- Solar irradiance: bell curve peaking at noon, scaled by cloud factor
- Cloud factor: sunny=1.0, partly_cloudy=0.7, cloudy=0.4

---

### `services/pricing.py`

**Function:** `generate_time_of_use_prices(date=None) → dict`

Generates a synthetic **time-of-use** pricing schedule.

```python
base = 0.12  # $/kWh
off_peak  = base * 0.75   # hours 0–5
mid_peak  = base * 1.10   # hours 6–17, 22–23
peak      = base * 1.75   # hours 18–21 (+ demand charge)
```

Returns a list of 24 hourly rate objects matching the `ElectricityPrices` schema.

---

### `services/database.py`

**Classes:** `EnergyUsage`, `SolarGeneration`, `DatabaseManager`

SQLAlchemy ORM for the local SQLite database. Migrated from `models/energy.py` to live **inside** the package.

`DatabaseManager` is initialized with a `db_path` from `Settings` — no hardcoded paths. Uses `lru_cache` in the tool layer to avoid re-instantiating per tool call.

Key methods:
- `create_tables()` — idempotent table creation
- `add_usage_record(...)` / `add_generation_record(...)` — write
- `get_usage_by_date_range(start, end)` — read with filter
- `get_recent_usage(hours)` / `get_recent_generation(hours)` — rolling window
- `count_usage_records()` / `count_generation_records()` — for bootstrap idempotency check

---

### `services/retrieval.py`

**Functions:**
- `ensure_vectorstore(persist_directory, document_paths) → Chroma`
- `list_document_paths(documents_dir) → list[str]`

Manages the ChromaDB vectorstore lifecycle. `ensure_vectorstore` is idempotent: if `chroma.sqlite3` already exists, it opens the existing store; otherwise it ingests documents and builds the index.

Chunk settings: `chunk_size=1000`, `chunk_overlap=200`

---

### `services/recommendations.py`

**Functions:**
- `compute_savings(device_type, current_kwh, optimized_kwh, price_per_kwh) → SavingsResult`
- `best_charging_windows(hourly_rates, solar_hourly, top_n) → list[dict]`
- `build_recommendation_context(usage, solar, weather, pricing, tips) → dict`

The **savings tool** delegates entirely to `compute_savings`. This means:
- The math is testable without invoking LangChain
- Notebooks can call `compute_savings` directly
- The formula is in one place — not duplicated across tools

`best_charging_windows` scores each hour by effective cost, optionally boosted by solar irradiance, and returns the cheapest N windows.

`build_recommendation_context` assembles all tool results into a single dict for LLM synthesis.

## Related Notes

- [[04_Tools]] — the tools that call these services
- [[06_Data_Layer]] — the database service in detail
- [[07_RAG_Pipeline]] — the retrieval service in detail
- [[09_Testing]] — how services are unit-tested
