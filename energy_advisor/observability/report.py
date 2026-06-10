"""Trace reader — turns the local JSONL traces into decisions.

A metric without a reader informs nothing. This CLI aggregates
agent_traces.jsonl by day, model and cost provenance so the numbers the
agent records all day can answer the operational questions: what is this
costing, how often does it fail, and where does the time go.

Usage:
    python -m energy_advisor.observability.report
    python -m energy_advisor.observability.report --traces path.jsonl --json out.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import Settings


def load_traces(path: str | Path) -> list[dict[str, Any]]:
    """Read JSONL traces, skipping unparseable lines (partial writes)."""
    traces: list[dict[str, Any]] = []
    file = Path(path)
    if not file.exists():
        return traces
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            traces.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return traces


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def summarize_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate traces into the operational summary."""
    total = len(traces)
    if total == 0:
        return {"total_requests": 0}

    successes = sum(1 for t in traces if t.get("success"))
    latencies = [float(t.get("latency_s", 0.0)) for t in traces]
    costs = [float(t.get("estimated_cost_usd", 0.0)) for t in traces]

    errors = Counter(t.get("error") for t in traces if t.get("error"))
    by_model: dict[str, dict[str, Any]] = {}
    by_day: dict[str, dict[str, Any]] = {}
    by_cost_source = Counter(t.get("cost_source", "unknown") for t in traces)
    tool_usage = Counter(name for t in traces for name in t.get("tools_used", []))

    for t in traces:
        model = t.get("model", "unknown")
        bucket = by_model.setdefault(model, {"requests": 0, "cost_usd": 0.0})
        bucket["requests"] += 1
        bucket["cost_usd"] += float(t.get("estimated_cost_usd", 0.0))

        day = datetime.fromtimestamp(float(t.get("created_at_epoch_s", 0.0))).strftime("%Y-%m-%d")
        daily = by_day.setdefault(
            day, {"requests": 0, "errors": 0, "cost_usd": 0.0, "latencies": []}
        )
        daily["requests"] += 1
        daily["cost_usd"] += float(t.get("estimated_cost_usd", 0.0))
        daily["latencies"].append(float(t.get("latency_s", 0.0)))
        if t.get("error"):
            daily["errors"] += 1

    for daily in by_day.values():
        lat = daily.pop("latencies")
        daily["avg_latency_s"] = round(sum(lat) / len(lat), 2) if lat else 0.0
        daily["cost_usd"] = round(daily["cost_usd"], 6)
    for bucket in by_model.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)

    return {
        "total_requests": total,
        "success_rate": round(successes / total, 3),
        "total_cost_usd": round(sum(costs), 6),
        "avg_latency_s": round(sum(latencies) / total, 2),
        "p95_latency_s": round(_percentile(latencies, 95), 2),
        "over_cost_budget": sum(1 for t in traces if t.get("over_cost_budget")),
        "over_latency_budget": sum(1 for t in traces if t.get("over_latency_budget")),
        "out_of_scope": sum(
            1 for t in traces if (t.get("metadata") or {}).get("scope_check") == "out_of_scope"
        ),
        "errors": dict(errors),
        "by_cost_source": dict(by_cost_source),
        "by_model": by_model,
        "by_day": dict(sorted(by_day.items())),
        "top_tools": dict(tool_usage.most_common(10)),
    }


def render_summary(summary: dict[str, Any]) -> str:
    """Human-readable rendering of the trace summary."""
    if summary.get("total_requests", 0) == 0:
        return "No traces found."
    lines = [
        "=" * 60,
        "EcoHome Agent Trace Report",
        "=" * 60,
        f"Requests        : {summary['total_requests']}  "
        f"(success rate {summary['success_rate']:.0%})",
        f"Total cost      : ${summary['total_cost_usd']:.4f}",
        f"Latency         : avg {summary['avg_latency_s']}s · p95 {summary['p95_latency_s']}s",
        f"Budget flags    : cost={summary['over_cost_budget']}  "
        f"latency={summary['over_latency_budget']}",
        f"Out of scope    : {summary['out_of_scope']}",
        "",
        "Cost provenance : "
        + ", ".join(f"{k}={v}" for k, v in summary["by_cost_source"].items()),
    ]
    if summary["errors"]:
        lines.append("Errors          : " + ", ".join(f"{k}={v}" for k, v in summary["errors"].items()))
    lines.append("")
    lines.append("Per day:")
    for day, d in summary["by_day"].items():
        lines.append(
            f"  {day}  requests={d['requests']:<4} errors={d['errors']:<3} "
            f"cost=${d['cost_usd']:<10} avg_latency={d['avg_latency_s']}s"
        )
    lines.append("")
    lines.append("Top tools:")
    for tool, count in summary["top_tools"].items():
        lines.append(f"  {tool:<28} {count}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Aggregate local agent traces.")
    parser.add_argument(
        "--traces", default=None,
        help="Path to agent_traces.jsonl (default: from settings).",
    )
    parser.add_argument("--json", default=None, help="Also write the summary to this JSON path.")
    args = parser.parse_args()

    traces_path = args.traces or Settings().observability_trace_path
    summary = summarize_traces(load_traces(traces_path))
    print(render_summary(summary))

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return summary


if __name__ == "__main__":
    main()
