from __future__ import annotations

import json
import re

from energy_advisor.evaluation.runner import (
    _append_eval_history,
    _default_output_path,
    artifact_versions,
    check_trajectory,
    compute_summary,
    is_ordered_subsequence,
)
from energy_advisor.evaluation.scenarios import Scenario

# ── B-2: prompt/contract versioning ──────────────────────────────────

def test_artifact_versions_changes_with_prompt() -> None:
    contract = {"scope": "x", "enforcement_mode": "block"}

    v1 = artifact_versions("prompt one", contract)
    v2 = artifact_versions("prompt two", contract)

    assert v1["prompt_hash"] != v2["prompt_hash"]
    assert v1["contract_hash"] == v2["contract_hash"]


def test_artifact_versions_changes_with_contract() -> None:
    v1 = artifact_versions("same prompt", {"enforcement_mode": "block"})
    v2 = artifact_versions("same prompt", {"enforcement_mode": "audit"})

    assert v1["contract_hash"] != v2["contract_hash"]
    assert v1["contract"] == {"enforcement_mode": "block"}


def test_eval_history_carries_version_fields(tmp_path) -> None:
    history_path = str(tmp_path / "eval_history.jsonl")
    summary = {"total_scenarios": 4, "trajectory_pass_rate": 1.0}
    report = {
        "generated_at": "2026-06-10T10:00:00",
        "model": "gpt-4o-mini",
        "quick_mode": True,
        "versions": {"prompt_hash": "abc123", "contract_hash": "def456", "git_commit": "f00ba4"},
    }

    _append_eval_history(summary, report, "run.json", history_path)

    entry = json.loads((tmp_path / "eval_history.jsonl").read_text().strip())
    assert entry["prompt_hash"] == "abc123"
    assert entry["contract_hash"] == "def456"
    assert entry["git_commit"] == "f00ba4"


def _scenario(required: list[str], order_matters: bool = True) -> Scenario:
    return Scenario(
        id="s1",
        question="q",
        required_tools=required,
        judge_rubric="r",
        order_matters=order_matters,
    )


# ── A-3: ordered trajectory tests ─────────────────────────────────────

def test_is_ordered_subsequence_allows_interleaving() -> None:
    assert is_ordered_subsequence(["a", "c"], ["a", "b", "c"]) is True


def test_is_ordered_subsequence_rejects_wrong_order() -> None:
    assert is_ordered_subsequence(["a", "b"], ["b", "a"]) is False


def test_is_ordered_subsequence_empty_required_always_passes() -> None:
    assert is_ordered_subsequence([], ["a"]) is True


def test_check_trajectory_fails_on_wrong_order_when_order_matters() -> None:
    result = check_trajectory(_scenario(["a", "b"]), ["b", "a"])

    assert result["missing_tools"] == []
    assert result["order_pass"] is False
    assert result["trajectory_pass"] is False


def test_check_trajectory_passes_wrong_order_when_order_is_free() -> None:
    result = check_trajectory(_scenario(["a", "b"], order_matters=False), ["b", "a"])

    assert result["order_pass"] is True
    assert result["trajectory_pass"] is True


def test_check_trajectory_reports_missing_tools() -> None:
    result = check_trajectory(_scenario(["a", "b"]), ["a"])

    assert result["missing_tools"] == ["b"]
    assert result["trajectory_pass"] is False


def test_check_trajectory_passes_exact_match() -> None:
    result = check_trajectory(_scenario(["a", "b"]), ["a", "x", "b"])

    assert result["trajectory_pass"] is True


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


# ── E-1: behavioral checks ────────────────────────────────────────────

from energy_advisor.evaluation.runner import (  # noqa: E402
    check_limitation_statement,
    check_rag_citations,
    extract_citations,
)


def test_limitation_statement_detected_in_portuguese() -> None:
    assert check_limitation_statement(
        "Não consegui acessar os dados de consumo devido a um erro no banco."
    ) is True


def test_limitation_statement_detected_with_accents_stripped() -> None:
    assert check_limitation_statement("Não foi possível obter os dados.") is True


def test_confident_fabricated_answer_has_no_limitation() -> None:
    assert check_limitation_statement(
        "Seu home office custou R$ 142,50 nos últimos 30 dias."
    ) is False


def test_extract_citations_finds_source_markers() -> None:
    answer = (
        "Dicas:\n- Use timer (source: tip_energy_savings.txt)\n"
        "- Modo eco (Source: tip_cost_reduction.txt)"
    )
    assert extract_citations(answer) == [
        "tip_energy_savings.txt", "tip_cost_reduction.txt",
    ]


def test_rag_citations_pass_when_expected_doc_cited() -> None:
    corpus = ["tip_energy_savings.txt", "tip_ev_charging.txt"]
    result = check_rag_citations(
        "Carregue de madrugada (source: tip_ev_charging.txt)",
        expected_sources=["tip_ev_charging.txt"],
        corpus=corpus,
    )
    assert result["expected_found"] is True
    assert result["fabricated"] == []


def test_rag_citations_flag_fabricated_source() -> None:
    result = check_rag_citations(
        "Dica (source: tip_inventado.txt)",
        expected_sources=["tip_ev_charging.txt"],
        corpus=["tip_ev_charging.txt"],
    )
    assert result["expected_found"] is False
    assert result["fabricated"] == ["tip_inventado.txt"]


def test_compute_summary_breaks_down_by_category() -> None:
    summary = compute_summary([
        {"trajectory_pass": True, "scenario_pass": True, "category": "core",
         "error": None, "elapsed_s": 1.0, "estimated_cost_usd": 0.0,
         "over_latency_budget": False, "over_cost_budget": False},
        {"trajectory_pass": True, "scenario_pass": False, "category": "adversarial",
         "error": None, "elapsed_s": 1.0, "estimated_cost_usd": 0.0,
         "over_latency_budget": False, "over_cost_budget": False},
    ])

    assert summary["scenario_pass_rate"] == 0.5
    assert summary["pass_by_category"]["core"] == {"passed": 1, "total": 1}
    assert summary["pass_by_category"]["adversarial"] == {"passed": 0, "total": 1}
