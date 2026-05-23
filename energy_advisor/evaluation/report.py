"""Load and pretty-print a saved evaluation report JSON.

Usage:
    python -m energy_advisor.evaluation.report eval_report.json
"""
from __future__ import annotations

import json
import sys


def print_report(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    s = report["summary"]
    print("\n" + "=" * 60)
    print("EcoHome Evaluation Report")
    print("=" * 60)
    print(f"Generated : {report['generated_at']}")
    print(f"Model     : {report['model']}")
    if report.get("judge_model"):
        print(f"Judge     : {report['judge_model']}")
    print(f"Scenarios : {s['total_scenarios']}  |  Errors: {s['errors']}")
    print(f"Avg time  : {s['avg_elapsed_s']}s per scenario")
    print()
    print(f"Trajectory pass rate : {s['trajectory_pass_rate']:.0%}  "
          f"({s['trajectory_pass_count']}/{s['total_scenarios']})")

    if "avg_judge_overall" in s:
        print()
        print("LLM-as-judge scores (1–5):")
        for key in ("grounding", "completeness", "actionability", "honesty", "overall"):
            bar = "█" * int(s[f"avg_judge_{key}"]) + "░" * (5 - int(s[f"avg_judge_{key}"]))
            print(f"  {key:<15} {bar}  {s[f'avg_judge_{key}']:.2f}")

    print()
    print("Per-scenario results:")
    for r in report["scenarios"]:
        icon = "✅" if r["trajectory_pass"] else "❌"
        called = ", ".join(r["called_tools"]) or "none"
        print(f"\n  {icon} [{r['scenario_id']}]  ({r['elapsed_s']}s)")
        print(f"     Q: {r['question'][:80]}{'...' if len(r['question']) > 80 else ''}")
        print(f"     Tools called : {called}")
        if r["missing_tools"]:
            print(f"     ⚠ Missing    : {', '.join(r['missing_tools'])}")
        if r.get("judge_scores"):
            j = r["judge_scores"]
            print(
                f"     Judge scores : grounding={j['grounding']} "
                f"completeness={j['completeness']} "
                f"actionability={j['actionability']} "
                f"honesty={j['honesty']} "
                f"→ overall={j['overall']}"
            )
            print(f"     Reasoning    : {j['reasoning']}")
        if r.get("error"):
            print(f"     ERROR: {r['error']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m energy_advisor.evaluation.report <path_to_report.json>")
        sys.exit(1)
    print_report(sys.argv[1])
