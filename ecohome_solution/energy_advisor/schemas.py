from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error: str


# ── Weather ──────────────────────────────────────────────────────────

class WeatherCurrent(BaseModel):
    temperature_c: float
    condition: str
    humidity: int
    wind_speed: float


class WeatherHourly(BaseModel):
    hour: int
    temperature_c: float
    condition: str
    solar_irradiance: float
    humidity: int
    wind_speed: float


class WeatherForecast(BaseModel):
    location: str
    forecast_days: int
    current: WeatherCurrent
    hourly: list[WeatherHourly]


# ── Electricity pricing ──────────────────────────────────────────────

class ElectricityRate(BaseModel):
    hour: int
    rate: float
    period: Literal["off_peak", "mid_peak", "peak"]
    demand_charge: float = 0.0


class ElectricityPrices(BaseModel):
    date: str
    pricing_type: str = "time_of_use"
    currency: str = "USD"
    unit: str = "per_kWh"
    hourly_rates: list[ElectricityRate]


# ── RAG retrieval ─────────────────────────────────────────────────────

class RagTip(BaseModel):
    rank: int
    content: str
    source: str = "unknown"
    relevance_score: str = "medium"


class RagSearchResult(BaseModel):
    query: str
    total_results: int
    tips: list[RagTip]


# ── Savings calculation ───────────────────────────────────────────────

class SavingsResult(BaseModel):
    device_type: str
    current_usage_kwh: float
    optimized_usage_kwh: float
    savings_kwh: float
    savings_usd: float
    savings_percentage: float
    price_per_kwh: float
    annual_savings_usd: float


# ── Agent request / response ──────────────────────────────────────────

class AgentRequest(BaseModel):
    question: str = Field(..., description="Natural-language question from the user.")
    context: str | None = Field(None, description="Optional extra context or constraints.")


class AgentResponse(BaseModel):
    recommendation: str = Field(..., description="Primary actionable recommendation.")
    reasoning: str = Field(..., description="Concise data-based rationale.")
    estimated_savings: dict[str, Any] | None = Field(
        None, description="Savings/impact estimate when available."
    )
    supporting_tips: list[dict[str, Any]] | None = Field(
        None, description="Relevant best-practice guidance."
    )
    limitations: str | None = Field(None, description="Assumptions and limitations.")
