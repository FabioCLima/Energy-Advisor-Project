from __future__ import annotations

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime configuration backed by environment variables.

    Precedence (highest to lowest): explicit env var → .env file → default value.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Model presets ────────────────────────────────────────────────
    model_preset: str = Field("fast", alias="ENERGY_ADVISOR_MODEL_PRESET")
    model_fast: str = Field("gpt-4o-mini", alias="ENERGY_ADVISOR_MODEL_FAST")
    model_quality: str = Field("gpt-4o", alias="ENERGY_ADVISOR_MODEL_QUALITY")
    model_custom: str | None = Field(None, alias="ENERGY_ADVISOR_MODEL")

    temperature: float = Field(0.0, alias="ENERGY_ADVISOR_TEMPERATURE")

    # ── API / endpoint ───────────────────────────────────────────────
    base_url: str | None = Field(None, alias="ENERGY_ADVISOR_BASE_URL")
    api_key: str | None = Field(None, alias="ENERGY_ADVISOR_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    vocareum_api_key: str | None = Field(None, alias="VOCAREUM_API_KEY")

    # ── Storage paths ────────────────────────────────────────────────
    db_path: str = Field("data/energy_data.db", alias="ENERGY_ADVISOR_DB_PATH")
    documents_dir: str = Field("data/documents", alias="ENERGY_ADVISOR_DOCS_DIR")
    vectorstore_dir: str = Field("data/vectorstore", alias="ENERGY_ADVISOR_VECTORSTORE_DIR")
    models_dir: str = Field("data/models", alias="ENERGY_ADVISOR_MODELS_DIR")
    aneel_cache_path: str = Field(
        "data/aneel_bandeiras_cache.json",
        alias="ENERGY_ADVISOR_ANEEL_CACHE_PATH",
    )
    aneel_fetch_enabled: bool = Field(True, alias="ENERGY_ADVISOR_ANEEL_FETCH_ENABLED")
    aneel_allow_insecure_ssl: bool = Field(False, alias="ENERGY_ADVISOR_ANEEL_ALLOW_INSECURE_SSL")

    # ── Forecasting / ML ─────────────────────────────────────────────
    usage_forecast_mode: str = Field("auto", alias="ENERGY_ADVISOR_USAGE_FORECAST_MODE")

    # ── Observability ────────────────────────────────────────────────
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # ── LangSmith tracing (optional) ────────────────────────────────
    langchain_api_key: str | None = Field(None, alias="LANGCHAIN_API_KEY")
    langchain_tracing_v2: str | None = Field(None, alias="LANGCHAIN_TRACING_V2")
    langchain_project: str | None = Field(None, alias="LANGCHAIN_PROJECT")
    langchain_endpoint: str | None = Field(None, alias="LANGCHAIN_ENDPOINT")

    # ── Validators ───────────────────────────────────────────────────
    @field_validator("model_preset", mode="before")
    @classmethod
    def _validate_preset(cls, value: str) -> str:
        v = (value or "").strip().lower()
        if v not in {"fast", "quality", "custom"}:
            raise ValueError("ENERGY_ADVISOR_MODEL_PRESET must be one of: fast, quality, custom")
        return v

    @field_validator("usage_forecast_mode", mode="before")
    @classmethod
    def _validate_usage_forecast_mode(cls, value: str) -> str:
        v = (value or "").strip().lower()
        if v not in {"baseline", "ml", "auto"}:
            raise ValueError("ENERGY_ADVISOR_USAGE_FORECAST_MODE must be one of: baseline, ml, auto")
        return v

    # ── Helpers ──────────────────────────────────────────────────────
    def selected_model(self) -> str:
        if self.model_preset == "fast":
            return self.model_fast
        if self.model_preset == "quality":
            return self.model_quality
        if not self.model_custom:
            raise ValueError(
                "ENERGY_ADVISOR_MODEL must be set when ENERGY_ADVISOR_MODEL_PRESET=custom"
            )
        return self.model_custom

    def selected_api_key(self) -> str | None:
        return self.api_key or self.vocareum_api_key or self.openai_api_key

    def usage_forecast_model_path(self, device_type: str | None = None) -> str:
        slug = (device_type or "all").strip().lower()
        return os.path.join(self.models_dir, f"usage_forecaster_{slug}.joblib")
