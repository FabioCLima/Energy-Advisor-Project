from __future__ import annotations

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .guardrails import GuardrailMode


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

    # ── Agent loop limits ────────────────────────────────────────────
    # Each ReAct iteration = one assistant step + one tools step. Without an
    # explicit cap, a model that keeps requesting tools runs until LangGraph's
    # implicit recursion limit aborts with a cryptic error — at full LLM cost.
    max_agent_iterations: int = Field(10, alias="ENERGY_ADVISOR_MAX_AGENT_ITERATIONS")
    llm_timeout_s: float = Field(60.0, alias="ENERGY_ADVISOR_LLM_TIMEOUT_S")
    llm_max_retries: int = Field(2, alias="ENERGY_ADVISOR_LLM_MAX_RETRIES")

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
    # Escape hatch for the ANEEL open-data endpoint, whose certificate chain is
    # intermittently broken. Affects only that fetch (never the LLM API), and the
    # client falls back to cached/bundled rates when disabled — prefer the default.
    aneel_allow_insecure_ssl: bool = Field(False, alias="ENERGY_ADVISOR_ANEEL_ALLOW_INSECURE_SSL")

    # ── Forecasting / ML ─────────────────────────────────────────────
    usage_forecast_mode: str = Field("auto", alias="ENERGY_ADVISOR_USAGE_FORECAST_MODE")
    bootstrap_vectorstore: bool = Field(False, alias="ENERGY_ADVISOR_BOOTSTRAP_VECTORSTORE")

    # ── Guardrails ───────────────────────────────────────────────────
    guardrail_mode: GuardrailMode = Field(GuardrailMode.BLOCK, alias="ENERGY_ADVISOR_GUARDRAIL_MODE")

    # ── API surface ──────────────────────────────────────────────────
    # When set, every /advisor/* request must send X-API-Key with this value.
    api_auth_key: str | None = Field(None, alias="ENERGY_ADVISOR_API_AUTH_KEY")
    # 0 disables. In-memory sliding window per client IP — per instance only;
    # a multi-replica deployment needs a shared store (e.g. Redis).
    rate_limit_per_minute: int = Field(0, alias="ENERGY_ADVISOR_RATE_LIMIT_PER_MINUTE")
    # Comma-separated allowed origins; "*" is a demo default, not a production one.
    cors_origins: str = Field("*", alias="ENERGY_ADVISOR_CORS_ORIGINS")
    # Provision demo assets (DB, sample data, ML artifacts) at API startup.
    bootstrap_on_start: bool = Field(True, alias="ENERGY_ADVISOR_BOOTSTRAP_ON_START")

    # ── Observability ────────────────────────────────────────────────
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    observability_enabled: bool = Field(True, alias="ENERGY_ADVISOR_OBSERVABILITY_ENABLED")
    observability_trace_path: str = Field(
        "data/observability/agent_traces.jsonl",
        alias="ENERGY_ADVISOR_OBSERVABILITY_TRACE_PATH",
    )
    # Calibrated against measured usage_metadata costs (gpt-4o-mini): multi-tool
    # scenarios legitimately reach ~$0.02/request. The previous $0.01 default was
    # set against the chars/4 heuristic, which understated real cost ~1000×.
    max_request_cost_usd: float = Field(0.05, alias="ENERGY_ADVISOR_MAX_REQUEST_COST_USD")
    max_request_latency_s: float = Field(20.0, alias="ENERGY_ADVISOR_MAX_REQUEST_LATENCY_S")
    # AUDIT: over-budget runs are flagged in traces only (observe-first rollout).
    # BLOCK: the ReAct loop is interrupted with BudgetExceeded (API → 429).
    # Latency stays flag-only: a request can't be un-spent, but it can be un-continued.
    budget_mode: GuardrailMode = Field(GuardrailMode.AUDIT, alias="ENERGY_ADVISOR_BUDGET_MODE")
    # JSON mapping model name → [input_usd_per_1k, output_usd_per_1k], merged over defaults.
    model_pricing_json: str | None = Field(None, alias="ENERGY_ADVISOR_MODEL_PRICING_JSON")

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

    def model_pricing(self) -> dict[str, tuple[float, float]] | None:
        """Optional pricing override parsed from ENERGY_ADVISOR_MODEL_PRICING_JSON."""
        if not self.model_pricing_json:
            return None
        import json

        raw = json.loads(self.model_pricing_json)
        return {model: (float(io[0]), float(io[1])) for model, io in raw.items()}
