---
tags: [ecohome, tools, langchain]
aliases: [Tools, Tool Layer]
---

# Tools

Tools are the **agent's hands** — the only way it can access real data. Each tool is a Python function decorated with `@tool` that validates inputs, calls a service, and returns a typed dict.

## Design Rule

> Tools should validate input, call services, serialize outputs, and handle errors — but should **not** become the main home of business logic.

```
Tool function
    │ validates input
    │ calls service
    │ returns model.model_dump()
    └ catches exceptions → returns {"error": "..."}
```

## Tool Inventory

### `get_weather_forecast`
**File:** `tools/weather.py`

| | |
|---|---|
| Purpose | Synthetic hourly weather for a location |
| Service | `services/forecasting.generate_hourly_forecast` |
| Output schema | `WeatherForecast` |

**Inputs:**
- `location: str` — city name
- `days: int = 3` — forecast days (1–7)

**Output fields:** `location`, `forecast_days`, `current` (temperature/humidity/wind), `hourly` (list of 24 hourly readings including `solar_irradiance`)

---

### `get_electricity_prices`
**File:** `tools/pricing.py`

| | |
|---|---|
| Purpose | Time-of-use pricing schedule |
| Service | `services/pricing.generate_time_of_use_prices` |
| Output schema | `ElectricityPrices` |

**Inputs:**
- `date: str | None = None` — YYYY-MM-DD, defaults to today

**TOU schedule:**
| Period | Hours | Rate |
|---|---|---|
| Off-peak | 00:00–06:00 | ~$0.09/kWh |
| Mid-peak | 06:00–18:00, 22:00–24:00 | ~$0.13/kWh |
| Peak | 18:00–22:00 | ~$0.21/kWh + demand charge |

---

### `query_energy_usage`
**File:** `tools/energy_data.py`

| | |
|---|---|
| Purpose | Historical device consumption from SQLite |
| Service | `services/database.DatabaseManager` |

**Inputs:**
- `start_date: str` — YYYY-MM-DD
- `end_date: str` — YYYY-MM-DD (inclusive)
- `device_type: str | None` — optional filter: `EV`, `HVAC`, `appliance`, `lighting`

**Returns:** total kWh, total cost, per-record breakdown

---

### `query_solar_generation`
**File:** `tools/energy_data.py`

| | |
|---|---|
| Purpose | Historical solar production from SQLite |
| Service | `services/database.DatabaseManager` |

**Inputs:** `start_date`, `end_date` (YYYY-MM-DD)

**Returns:** total kWh generated, average daily kWh, per-record detail with irradiance and weather

---

### `get_recent_energy_summary`
**File:** `tools/energy_data.py`

| | |
|---|---|
| Purpose | Quick rolling-window summary of usage + generation |
| Service | `services/database.DatabaseManager` |

**Inputs:**
- `hours: int = 24` — look-back window (1–8760)

**Returns:** total consumption by device type, total solar generation

---

### `search_energy_tips`
**File:** `tools/rag.py`

| | |
|---|---|
| Purpose | Semantic search over knowledge base |
| Service | `services/retrieval.ensure_vectorstore` |
| Output schema | `RagSearchResult` |

**Inputs:**
- `query: str` — natural-language question
- `max_results: int = 5` — number of chunks to retrieve

**Returns:** ranked tips with source file, content excerpt, relevance score

---

### `calculate_energy_savings`
**File:** `tools/savings.py`

| | |
|---|---|
| Purpose | Savings calculation for a device optimization |
| Service | `services/recommendations.compute_savings` |
| Output schema | `SavingsResult` |

**Inputs:**
- `device_type: str`
- `current_usage_kwh: float`
- `optimized_usage_kwh: float`
- `price_per_kwh: float = 0.12`

**Returns:** `savings_kwh`, `savings_usd`, `savings_percentage`, `annual_savings_usd`

## Error Handling Pattern

Every tool wraps its logic in `try/except` and returns `{"error": "..."}` on failure. This lets the agent detect errors and state limitations explicitly rather than crashing.

```python
try:
    result = service_call(...)
    return Model.model_validate(result).model_dump()
except Exception as exc:
    logger.exception("tool failed")
    return {"error": f"Failed: {exc}"}
```

## Related Notes

- [[05_Services]] — the services that tools delegate to
- [[03_Agent_and_Prompts]] — how the agent selects tools
- [[07_RAG_Pipeline]] — how the RAG tool works internally
