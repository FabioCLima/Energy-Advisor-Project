from __future__ import annotations

import json
import re

from energy_advisor.evaluation.runner import (
    _append_eval_history,
    _default_output_path,
    compute_summary,
)


def test_compute_summary_includes_operational_quality_gates() -> None:
    summary = compute_summary([
        {
            "trajectory_pass": True,
            "error": None,
            "elapsed_s": 1.0,
            "estimated_cost_usd": 0.0001,
            "over_latency_budget": False,
            "over_cost_budget": False,
        },
        {
            "trajectory_pass": False,
            "error": None,
            "elapsed_s": 3.0,
            "estimated_cost_usd": 0.0003,
            "over_latency_budget": True,
            "over_cost_budget": False,
        },
    ])

    assert summary["trajectory_pass_rate"] == 0.5
    assert summary["avg_elapsed_s"] == 2.0
    assert summary["total_estimated_cost_usd"] == 0.0004
    assert summary["avg_estimated_cost_usd"] == 0.0002
    assert summary["latency_budget_violations"] == 1
    assert summary["cost_budget_violations"] == 0
    assert summary["quality_gates_pass"] is False


def test_compute_summary_passes_quality_gates_when_operational_limits_hold() -> None:
    summary = compute_summary([
        {
            "trajectory_pass": True,
            "error": None,
            "elapsed_s": 1.0,
            "estimated_cost_usd": 0.0001,
            "over_latency_budget": False,
            "over_cost_budget": False,
        }
    ])

    assert summary["quality_gates_pass"] is True


# ── E-1: timestamp path + eval_history tests ──────────────────────────

def test_default_output_path_has_timestamp_format() -> None:
    path = _default_output_path()

    assert path.startswith("eval_report_")
    assert path.endswith(".json")
    # YYYYMMDD_HHMMSS — 15 digit chars + underscore
    assert re.search(r"eval_report_\d{8}_\d{6}\.json", path)


def test_append_eval_history_creates_file_and_writes_entry(tmp_path) -> None:
    history_path = str(tmp_path / "eval_history.jsonl")
    summary = {
        "total_scenarios": 4,
        "trajectory_pass_rate": 0.75,
        "avg_judge_overall": 4.2,
    }
    report = {
        "generated_at": "2026-05-26T14:32:00",
        "model": "gpt-4o-mini",
        "quick_mode": True,
        "summary": summary,
    }

    _append_eval_history(summary, report, "eval_report_20260526_143200.json", history_path)

    lines = (tmp_path / "eval_history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["trajectory_pass_rate"] == 0.75
    assert entry["avg_judge_overall"] == 4.2
    assert entry["report_file"] == "eval_report_20260526_143200.json"
    assert entry["model"] == "gpt-4o-mini"


def test_append_eval_history_accumulates_multiple_runs(tmp_path) -> None:
    history_path = str(tmp_path / "eval_history.jsonl")
    base_summary = {"total_scenarios": 4, "trajectory_pass_rate": 0.5}
    base_report = {"generated_at": "2026-05-26T10:00:00", "model": "gpt-4o-mini", "quick_mode": False}

    _append_eval_history(base_summary, base_report, "run1.json", history_path)
    _append_eval_history(
        {**base_summary, "trajectory_pass_rate": 0.75},
        {**base_report, "generated_at": "2026-05-26T11:00:00"},
        "run2.json",
        history_path,
    )

    lines = (tmp_path / "eval_history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["report_file"] == "run1.json"
    assert json.loads(lines[1])["trajectory_pass_rate"] == 0.75


def test_append_eval_history_none_judge_score_is_preserved(tmp_path) -> None:
    history_path = str(tmp_path / "eval_history.jsonl")
    summary = {"total_scenarios": 4, "trajectory_pass_rate": 1.0}
    report = {"generated_at": "2026-05-26T09:00:00", "model": "gpt-4o-mini", "quick_mode": True}

    _append_eval_history(summary, report, "run.json", history_path)

    entry = json.loads((tmp_path / "eval_history.jsonl").read_text().strip())
    assert entry["avg_judge_overall"] is None
