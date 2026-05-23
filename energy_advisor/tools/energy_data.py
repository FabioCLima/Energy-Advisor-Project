from __future__ import annotations

import functools
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager


@functools.lru_cache(maxsize=1)
def _get_db(db_path: str) -> DatabaseManager:
    """Lazy, cached DatabaseManager — instantiated once per db_path."""
    return DatabaseManager(db_path=db_path)


def _db() -> DatabaseManager:
    settings = Settings()
    return _get_db(settings.db_path)


@tool
def query_energy_usage(
    start_date: str,
    end_date: str,
    device_name: str | None = None,
    usage_pattern: str | None = None,
) -> dict[str, Any]:
    """Query energy usage from the SQLite database, aggregated by device.

    Returns a summary with totals and a per-device breakdown — NOT raw records.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format (inclusive).
        device_name: Optional exact device name filter, e.g. 'Tesla Model 3 Long Range'.
        usage_pattern: Optional filter — one of 'always_on', 'presence_dependent', 'scheduled'.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    try:
        logger.debug(
            "query_energy_usage | {} → {} | device_name={} pattern={}",
            start_date, end_date, device_name, usage_pattern,
        )
        db = _db()
        records = db.get_usage_by_date_range(start_dt, end_dt)

        if device_name:
            records = [r for r in records if r.device_name == device_name]
        if usage_pattern:
            records = [r for r in records if (r.usage_pattern or "") == usage_pattern]

        # Aggregate by device — avoid sending thousands of raw rows to the LLM
        by_device: dict[str, dict[str, Any]] = {}
        for r in records:
            key = r.device_name or r.device_type or "unknown"
            bucket = by_device.setdefault(key, {
                "device_name": key,
                "device_type": r.device_type,
                "usage_pattern": r.usage_pattern,
                "consumption_kwh": 0.0,
                "cost_brl": 0.0,
                "record_count": 0,
            })
            bucket["consumption_kwh"] += r.consumption_kwh
            bucket["cost_brl"] += r.cost_brl or 0.0
            bucket["record_count"] += 1

        device_breakdown = sorted(
            [
                {**v,
                 "consumption_kwh": round(v["consumption_kwh"], 2),
                 "cost_brl": round(v["cost_brl"], 2)}
                for v in by_device.values()
            ],
            key=lambda x: x["cost_brl"],
            reverse=True,
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "filters": {"device_name": device_name, "usage_pattern": usage_pattern},
            "total_consumption_kwh": round(sum(r.consumption_kwh for r in records), 2),
            "total_cost_brl": round(sum(r.cost_brl or 0.0 for r in records), 2),
            "device_breakdown": device_breakdown,
        }
    except Exception as exc:
        logger.exception("query_energy_usage failed")
        return {"error": f"Failed to query energy usage: {exc}"}


@tool
def query_solar_generation(start_date: str, end_date: str) -> dict[str, Any]:
    """Query solar generation data from the local SQLite database for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format (inclusive).
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    try:
        logger.debug("query_solar_generation | {} → {}", start_date, end_date)
        db = _db()
        records = db.get_generation_by_date_range(start_dt, end_dt)
        days = max(1, (end_dt - start_dt).days)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_records": len(records),
            "total_generation_kwh": round(sum(r.generation_kwh for r in records), 2),
            "average_daily_generation_kwh": round(
                sum(r.generation_kwh for r in records) / days, 2
            ),
            "records": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "generation_kwh": r.generation_kwh,
                    "weather_condition": r.weather_condition,
                    "temperature_c": r.temperature_c,
                    "solar_irradiance": r.solar_irradiance,
                }
                for r in records
            ],
        }
    except Exception as exc:
        logger.exception("query_solar_generation failed")
        return {"error": f"Failed to query solar generation: {exc}"}


@tool
def get_recent_energy_summary(hours: int = 24) -> dict[str, Any]:
    """Get a summary of recent energy usage and solar generation.

    Args:
        hours: Look-back window in hours (default 24).
    """
    if hours < 1 or hours > 8760:
        return {"error": "hours must be between 1 and 8760."}

    try:
        logger.debug("get_recent_energy_summary | hours={}", hours)
        db = _db()
        usage_records = db.get_recent_usage(hours)
        generation_records = db.get_recent_generation(hours)

        device_breakdown: dict[str, Any] = {}
        for r in usage_records:
            key = r.device_type or "unknown"
            bucket = device_breakdown.setdefault(
                key, {"consumption_kwh": 0.0, "cost_brl": 0.0, "records": 0}
            )
            bucket["consumption_kwh"] += r.consumption_kwh
            bucket["cost_brl"] += r.cost_brl or 0.0
            bucket["records"] += 1

        for v in device_breakdown.values():
            v["consumption_kwh"] = round(v["consumption_kwh"], 2)
            v["cost_brl"] = round(v["cost_brl"], 2)

        return {
            "time_period_hours": hours,
            "usage": {
                "total_consumption_kwh": round(sum(r.consumption_kwh for r in usage_records), 2),
                "total_cost_brl": round(sum(r.cost_brl or 0.0 for r in usage_records), 2),
                "device_breakdown": device_breakdown,
            },
            "generation": {
                "total_generation_kwh": round(
                    sum(r.generation_kwh for r in generation_records), 2
                ),
            },
        }
    except Exception as exc:
        logger.exception("get_recent_energy_summary failed")
        return {"error": f"Failed to get energy summary: {exc}"}
