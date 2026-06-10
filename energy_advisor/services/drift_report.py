"""Drift report runner — turns the drift library into a scheduled process.

drift_monitor.py compares two dataframes; this module owns the *process*:
load baseline vs current windows from the energy database, run the monitor
over usage and solar series, and persist a JSON report. Scheduled weekly by
.github/workflows/drift.yml; drift is a warning, not a build failure —
detecting change is information, deciding what to do about it is human work.

Usage:
    python -m energy_advisor.services.drift_report
    python -m energy_advisor.services.drift_report --baseline-days 30 --current-days 30
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine

from ..config import Settings
from .drift_monitor import monitor_energy_drift


def _load_window(
    engine: Any, table: str, value_column: str, start: datetime, end: datetime
) -> pd.DataFrame:
    query = (
        f"SELECT timestamp, {value_column} FROM {table} "  # noqa: S608 — fixed identifiers
        "WHERE timestamp >= :start AND timestamp < :end"
    )
    return pd.read_sql_query(
        query, engine, params={"start": str(start), "end": str(end)}
    )


def build_drift_report(
    settings: Settings | None = None,
    *,
    baseline_days: int = 30,
    current_days: int = 30,
    mean_shift_threshold: float = 0.25,
) -> dict[str, Any]:
    """Compare the last `current_days` against the preceding `baseline_days`.

    Raises ValueError when either window is empty — silence about missing
    data is exactly the failure mode a drift process exists to prevent.
    """
    settings = settings or Settings()
    engine = create_engine(f"sqlite:///{settings.db_path}")

    now = datetime.now()
    current_start = now - timedelta(days=current_days)
    baseline_start = current_start - timedelta(days=baseline_days)

    sections: dict[str, Any] = {}
    drift_detected = False
    for name, table, column in (
        ("usage", "energy_usage", "consumption_kwh"),
        ("solar", "solar_generation", "generation_kwh"),
    ):
        baseline = _load_window(engine, table, column, baseline_start, current_start)
        current = _load_window(engine, table, column, current_start, now)
        if baseline.empty or current.empty:
            raise ValueError(
                f"Empty {name} window (baseline={len(baseline)}, current={len(current)} rows). "
                "Run the bootstrap or adjust the window sizes."
            )
        report = monitor_energy_drift(
            baseline, current,
            feature_columns=[column],
            mean_shift_threshold=mean_shift_threshold,
        )
        sections[name] = {
            "rows_baseline": len(baseline),
            "rows_current": len(current),
            **report.to_dict(),
        }
        drift_detected = drift_detected or report.drift_detected

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "baseline_window": [str(baseline_start.date()), str(current_start.date())],
        "current_window": [str(current_start.date()), str(now.date())],
        "mean_shift_threshold": mean_shift_threshold,
        "drift_detected": drift_detected,
        "series": sections,
    }


def _print_summary(report: dict[str, Any]) -> None:
    print("=" * 60)
    print("EcoHome Drift Report")
    print("=" * 60)
    print(f"Baseline : {report['baseline_window'][0]} → {report['baseline_window'][1]}")
    print(f"Current  : {report['current_window'][0]} → {report['current_window'][1]}")
    for name, section in report["series"].items():
        for feature in section["feature_results"]:
            flag = "DRIFT" if feature["drift_detected"] else "ok"
            print(
                f"  {name:<6} {feature['feature']:<18} "
                f"baseline={feature['baseline_mean']:<10} current={feature['current_mean']:<10} "
                f"Δ={feature['relative_change']:+.1%}  [{flag}]"
            )
    print(f"Result   : {'⚠️ DRIFT DETECTED' if report['drift_detected'] else '✅ no drift'}")
    print("=" * 60)


def main() -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run the energy drift report.")
    parser.add_argument("--output", default=None, help="JSON output path (default: timestamped).")
    parser.add_argument("--baseline-days", type=int, default=30)
    parser.add_argument("--current-days", type=int, default=30)
    parser.add_argument("--threshold", type=float, default=0.25, help="Mean shift threshold.")
    args = parser.parse_args()

    report = build_drift_report(
        baseline_days=args.baseline_days,
        current_days=args.current_days,
        mean_shift_threshold=args.threshold,
    )

    output = args.output or (
        f"data/observability/drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success("Drift report saved → {}", output)

    _print_summary(report)
    return report


if __name__ == "__main__":
    main()
