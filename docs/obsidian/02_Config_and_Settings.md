---
tags: [ecohome, config, settings, pydantic]
aliases: [Config, Settings, Environment]
---

# Config and Settings

All configuration is centralized in `energy_advisor/config.py` using **Pydantic Settings**.

## Why Pydantic Settings?

Pydantic Settings reads environment variables and validates them at startup. If a required value is missing or has the wrong type, the application fails *immediately* with a clear error — not silently at runtime when a tool is called.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
```

## Available Settings

### Model Presets

| Env Var | Default | Purpose |
|---|---|---|
| `ENERGY_ADVISOR_MODEL_PRESET` | `fast` | Active preset: `fast`, `quality`, or `custom` |
| `ENERGY_ADVISOR_MODEL_FAST` | `gpt-4o-mini` | Model for fast preset |
| `ENERGY_ADVISOR_MODEL_QUALITY` | `gpt-4o` | Model for quality preset |
| `ENERGY_ADVISOR_MODEL` | — | Model for custom preset (required if preset=custom) |
| `ENERGY_ADVISOR_TEMPERATURE` | `0.0` | LLM temperature |

### API Keys

| Env Var | Purpose |
|---|---|
| `ENERGY_ADVISOR_API_KEY` | Explicit project key (highest priority) |
| `VOCAREUM_API_KEY` | Vocareum proxy key |
| `OPENAI_API_KEY` | Standard OpenAI key (fallback) |
| `ENERGY_ADVISOR_BASE_URL` | Custom API endpoint (e.g. Vocareum proxy) |

API key resolution order: `ENERGY_ADVISOR_API_KEY` → `VOCAREUM_API_KEY` → `OPENAI_API_KEY`

### Storage Paths

| Env Var | Default | Purpose |
|---|---|---|
| `ENERGY_ADVISOR_DB_PATH` | `data/energy_data.db` | SQLite database file |
| `ENERGY_ADVISOR_DOCS_DIR` | `data/documents` | RAG knowledge documents |
| `ENERGY_ADVISOR_VECTORSTORE_DIR` | `data/vectorstore` | ChromaDB persist directory |

### Observability

| Env Var | Default | Purpose |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Loguru log level |
| `LANGCHAIN_API_KEY` | — | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | — | Enable LangSmith (`true`) |
| `LANGCHAIN_PROJECT` | — | LangSmith project name |
| `LANGCHAIN_ENDPOINT` | — | LangSmith API endpoint |

## `.env` Template

```dotenv
# API Keys
OPENAI_API_KEY=sk-...
# VOCAREUM_API_KEY=
# ENERGY_ADVISOR_BASE_URL=https://openai.vocareum.com/v1

# Model
ENERGY_ADVISOR_MODEL_PRESET=fast

# Logging
LOG_LEVEL=INFO

# LangSmith (optional)
# LANGCHAIN_API_KEY=lsv2_...
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT=ecohome-energy-advisor
# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

## Pydantic v1 → v2 Migration Notes

The project was updated from Pydantic v1 to v2. Key changes:

| v1 | v2 |
|---|---|
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` |
| `class Config: env_file = ".env"` | `model_config = SettingsConfigDict(env_file=".env")` |
| `@validator("field")` | `@field_validator("field", mode="before")` |
| `model.dict()` | `model.model_dump()` |
| `Model.parse_obj(data)` | `Model.model_validate(data)` |
| `Optional[str]` | `str \| None` |
| `List[...]`, `Dict[...]` | `list[...]`, `dict[...]` |

## Related Notes

- [[01_Architecture]] — where settings fit in the layer model
- [[08_Bootstrap]] — how Settings drives the bootstrap process
- [[09_Testing]] — how test fixtures override Settings
