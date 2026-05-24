from __future__ import annotations

from energy_advisor.evaluation.runner import compute_summary


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
