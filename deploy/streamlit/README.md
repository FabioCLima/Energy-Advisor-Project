# Streamlit Cloud Deployment

## App target
- Main file: `streamlit_app.py`
- Python version: `3.12`

## Required secrets
Add these in Streamlit Cloud > App settings > Secrets:

```toml
OPENAI_API_KEY = "sk-..."
ENERGY_ADVISOR_MODEL_PRESET = "fast"
ENERGY_ADVISOR_USAGE_FORECAST_MODE = "auto"
```

## Optional secrets
```toml
LANGCHAIN_API_KEY = "..."
LANGCHAIN_TRACING_V2 = "true"
LANGCHAIN_PROJECT = "energy-advisor"
ENERGY_ADVISOR_ANEEL_FETCH_ENABLED = "true"
```

## Boot behavior
On first boot, the app provisions:
- SQLite tables
- João sample data
- local forecasting model artifacts

The vectorstore bootstrap is skipped on app startup unless you explicitly enable it in code for a surface that has embedding credentials and longer cold-start tolerance.

## Notes
- Dashboard works without an OpenAI key; the chat tab does not.
- If ANEEL fetch fails, the app falls back to bundled values and shows that provenance in the UI.
