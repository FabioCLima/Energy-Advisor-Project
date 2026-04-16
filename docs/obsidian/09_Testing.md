---
tags: [ecohome, testing, pytest]
aliases: [Testing, Tests, Unit Tests]
---

# Testing

The test suite covers all core business logic — configuration, pricing, forecasting, savings calculations, and database operations.

## Running Tests

```bash
cd ecohome_solution
pytest tests/ -v
```

Expected output: **37 tests passing** in ~0.3 seconds.

## Test File Map

| File | What it tests |
|---|---|
| `conftest.py` | Shared fixtures |
| `test_config.py` | Settings loading, presets, API key priority |
| `test_pricing.py` | TOU schedule correctness (24 hours, peak/off-peak/mid-peak) |
| `test_forecasting.py` | Determinism, irradiance bounds, clamping |
| `test_savings.py` | Math correctness, edge cases, annual projection |
| `test_database.py` | CRUD operations, date range filtering, idempotency |

## Key Fixtures (`conftest.py`)

```python
@pytest.fixture()
def tmp_db_path(tmp_path) -> str:
    # Returns path to a temp .db file — isolated per test
    return str(tmp_path / "test_energy.db")

@pytest.fixture()
def test_settings(tmp_db_path, tmp_path) -> Settings:
    # Settings pointing to temp directories
    # Overrides env vars so tests don't need .env
    os.environ["ENERGY_ADVISOR_DB_PATH"] = tmp_db_path
    return Settings()

@pytest.fixture()
def db(tmp_db_path) -> DatabaseManager:
    # Pre-initialised DatabaseManager with tables created
    manager = DatabaseManager(db_path=tmp_db_path)
    manager.create_tables()
    return manager
```

Each test gets a **fresh, isolated database** via `tmp_path`. Tests never share state or touch the real `data/energy_data.db`.

## Notable Test Cases

### Determinism test (forecasting)
```python
def test_deterministic_output():
    r1 = generate_hourly_forecast(location="London", days=3)
    r2 = generate_hourly_forecast(location="London", days=3)
    assert r1["hourly"] == r2["hourly"]  # Same seed → same output
```

### Zero-division guard (savings)
```python
def test_zero_current_usage():
    result = compute_savings("Lighting", 0.0, 0.0, 0.12)
    assert result.savings_percentage == 0.0  # No division by zero
```

### Date boundary awareness (database)
```python
def test_date_range_filter(db):
    # end_date must cover the record's timestamp
    results = db.get_usage_by_date_range(
        datetime(2025, 3, 2),
        datetime(2025, 3, 4, 23, 59, 59)  # end-of-day, not midnight
    )
    assert len(results) == 3
```

### API key priority (config)
```python
def test_api_key_priority(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_API_KEY", "explicit-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    s = Settings()
    assert s.selected_api_key() == "explicit-key"
```

## What's Not Tested

- The `EnergyAdvisorAgent` class — requires a live OpenAI API call
- The `search_energy_tips` tool — requires OpenAI embeddings
- The `get_weather_forecast` / `get_electricity_prices` tools — thin wrappers; services are tested

These are better covered by integration tests or evaluation notebooks (see `03_run_and_evaluate.ipynb`).

## Ruff (Linting)

```bash
ruff check energy_advisor/ tests/   # Check for issues
ruff format energy_advisor/ tests/  # Auto-format
```

Ruff is configured in `pyproject.toml`:
- Rules: `E`, `F`, `I` (imports), `B` (bugbear), `UP` (pyupgrade to Python 3.12)
- Python target: 3.12 (enables `str | None` instead of `Optional[str]`)

## Related Notes

- [[05_Services]] — what the services being tested do
- [[06_Data_Layer]] — DatabaseManager behavior tested in `test_database.py`
- [[02_Config_and_Settings]] — Settings behavior tested in `test_config.py`
