"""Evaluation runner for the EcoHome Energy Advisor agent.

Usage:
    python -m energy_advisor.evaluation.runner --output eval_report.json
    python -m energy_advisor.evaluation.runner --output eval_report.json --no-judge
    python -m energy_advisor.evaluation.runner --output eval_report.json --quick
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from ..agent import EnergyAdvisorAgent
from ..config import Settings
from ..observability import cost_from_tokens, estimate_llm_cost, extract_token_usage
from ..prompts import SYSTEM_INSTRUCTIONS
from .scenarios import ALL_SCENARIOS, QUICK_SCENARIOS, Scenario

# ── Judge output schema ───────────────────────────────────────────────

class JudgeScores(BaseModel):
    grounding: int = Field(..., ge=1, le=5, description="Numbers traceable to tool output")
    completeness: int = Field(..., ge=1, le=5, description="Follows Recommendation/Why/Savings/Tips/Limitations")
    actionability: int = Field(..., ge=1, le=5, description="Recommendation is concrete and executable")
    honesty: int = Field(..., ge=1, le=5, description="Assumptions and limitations stated explicitly")
    reasoning: str = Field(..., description="One sentence justifying the scores")


_JUDGE_PROMPT = """\
You are an independent evaluator of an AI energy advisor. Score the response below on four criteria (1=poor, 5=excellent).

Question: {question}

Agent response:
{response}

Rubric hint: {rubric}

Scoring guide:
- grounding (1-5): Are specific numbers (kWh, R$, hours) traceable to data, not invented?
- completeness (1-5): Does the response follow the expected structure (Recommendation / Why / Savings / Tips / Limitations)?
- actionability (1-5): Is the recommendation concrete enough to act on immediately?
- honesty (1-5): Are assumptions and data limitations stated explicitly?

Return JSON with keys: grounding, completeness, actionability, honesty (each 1-5), reasoning (one sentence).
"""


# ── Core extraction ───────────────────────────────────────────────────

def extract_tool_calls(result: dict[str, Any]) -> list[str]:
    """Return list of tool names called, in order, from LangGraph state."""
    called: list[str] = []
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            called.extend(tc["name"] for tc in msg.tool_calls)
    return called


def get_final_answer(result: dict[str, Any]) -> str:
    """Return the last AI message content (final response to user)."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content
    return ""


def is_ordered_subsequence(required: list[str], called: list[str]) -> bool:
    """True when `required` appears in `called` in order, allowing interleaving.

    Example: required=[A, C] matches called=[A, B, C] but not called=[C, A].
    """
    it = iter(called)
    return all(tool in it for tool in required)


def check_trajectory(scenario: Scenario, called_tools: list[str]) -> dict[str, Any]:
    """Evaluate a scenario's tool trajectory against the agent's actual calls.

    Two independent checks, reported separately so a report reader can tell
    *why* a trajectory failed:
    - membership: every required tool was called (missing_tools empty)
    - order: required tools appear as an ordered subsequence (when order_matters)
    """
    missing_tools = [t for t in scenario.required_tools if t not in called_tools]
    order_pass = (
        is_ordered_subsequence(scenario.required_tools, called_tools)
        if scenario.order_matters
        else True
    )
    return {
        "missing_tools": missing_tools,
        "order_pass": order_pass,
        "trajectory_pass": not missing_tools and order_pass,
    }


# ── LLM-as-judge ─────────────────────────────────────────────────────

def run_judge(
    question: str,
    response: str,
    rubric: str,
    settings: Settings,
) -> JudgeScores | None:
    """Score a response using a separate LLM judge. Returns None on failure."""
    try:
        llm = ChatOpenAI(
            model=settings.model_quality,  # always use the stronger model as judge
            temperature=0.0,
            base_url=settings.base_url,
            api_key=settings.selected_api_key(),
        )
        judge = llm.with_structured_output(JudgeScores)
        prompt = _JUDGE_PROMPT.format(
            question=question,
            response=response,
            rubric=rubric,
        )
        return judge.invoke(prompt)
    except Exception as exc:
        logger.warning("Judge failed for question '{}': {}", question[:60], exc)
        return None


# ── Per-scenario evaluation ───────────────────────────────────────────

def evaluate_scenario(
    scenario: Scenario,
    agent: EnergyAdvisorAgent,
    settings: Settings,
    use_judge: bool,
) -> dict[str, Any]:
    logger.info("Running scenario: {}", scenario.id)
    t0 = time.time()

    try:
        result = agent.invoke(scenario.question)
        elapsed = round(time.time() - t0, 2)
        called_tools = extract_tool_calls(result)
        final_answer = get_final_answer(result)
        error = None
    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        called_tools = []
        final_answer = ""
        error = str(exc)
        logger.error("Scenario {} failed: {}", scenario.id, exc)

    usage = extract_token_usage(result) if not error else None
    if usage is not None:
        cost_estimate = cost_from_tokens(
            settings.selected_model(), usage[0], usage[1], pricing=settings.model_pricing()
        )
    else:
        cost_estimate = estimate_llm_cost(
            settings.selected_model(), scenario.question, final_answer,
            pricing=settings.model_pricing(),
        )
    trajectory = check_trajectory(scenario, called_tools)
    over_latency_budget = elapsed > settings.max_request_latency_s
    over_cost_budget = cost_estimate.estimated_cost_usd > settings.max_request_cost_usd

    judge_scores: dict[str, Any] | None = None
    if use_judge and final_answer and not error:
        scores = run_judge(scenario.question, final_answer, scenario.judge_rubric, settings)
        if scores:
            judge_scores = {
                "grounding":      scores.grounding,
                "completeness":   scores.completeness,
                "actionability":  scores.actionability,
                "honesty":        scores.honesty,
                "reasoning":      scores.reasoning,
                "overall":        round(
                    (scores.grounding + scores.completeness +
                     scores.actionability + scores.honesty) / 4, 2
                ),
            }

    return {
        "scenario_id":     scenario.id,
        "question":        scenario.question,
        "tags":            scenario.tags,
        "required_tools":  scenario.required_tools,
        "order_matters":   scenario.order_matters,
        "called_tools":    called_tools,
        "trajectory_pass": trajectory["trajectory_pass"],
        "order_pass":      trajectory["order_pass"],
        "missing_tools":   trajectory["missing_tools"],
        "final_answer":    final_answer,
        "elapsed_s":       elapsed,
        "input_tokens_estimate": cost_estimate.input_tokens,
        "output_tokens_estimate": cost_estimate.output_tokens,
        "estimated_cost_usd": cost_estimate.estimated_cost_usd,
        "cost_source":     cost_estimate.cost_source,
        "over_latency_budget": over_latency_budget,
        "over_cost_budget": over_cost_budget,
        "error":           error,
        "judge_scores":    judge_scores,
    }


# ── Summary computation ───────────────────────────────────────────────

def compute_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    traj_pass = sum(1 for r in results if r["trajectory_pass"])
    scored = [r["judge_scores"] for r in results if r.get("judge_scores")]

    cost_values = [r.get("estimated_cost_usd", 0.0) for r in results]
    latency_violations = sum(1 for r in results if r.get("over_latency_budget"))
    cost_violations = sum(1 for r in results if r.get("over_cost_budget"))
    summary: dict[str, Any] = {
        "total_scenarios":        total,
        "trajectory_pass_count":  traj_pass,
        "trajectory_pass_rate":   round(traj_pass / total, 2) if total else 0,
        "errors":                 sum(1 for r in results if r["error"]),
        "avg_elapsed_s":          round(sum(r["elapsed_s"] for r in results) / total, 2) if total else 0,
        "total_estimated_cost_usd": round(sum(cost_values), 6),
        "avg_estimated_cost_usd": round(sum(cost_values) / total, 6) if total else 0,
        "latency_budget_violations": latency_violations,
        "cost_budget_violations": cost_violations,
        "quality_gates_pass": (latency_violations == 0 and cost_violations == 0 and sum(1 for r in results if r["error"]) == 0),
    }

    if scored:
        for key in ("grounding", "completeness", "actionability", "honesty", "overall"):
            summary[f"avg_judge_{key}"] = round(
                sum(s[key] for s in scored) / len(scored), 2
            )

    return summary


# ── Helpers ───────────────────────────────────────────────────────────

def artifact_versions(instructions: str, contract_dict: dict[str, Any]) -> dict[str, Any]:
    """Identify the prompt + contract + commit that produced an eval report.

    Without these, two entries in eval_history.jsonl are not comparable — the
    system prompt may have changed between runs. Reproducibility for LLM
    systems means versioning the trio (model, prompt, eval data), not just code.
    """
    prompt_hash = hashlib.sha256(instructions.encode("utf-8")).hexdigest()[:12]
    contract_hash = hashlib.sha256(
        json.dumps(contract_dict, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            commit = None
    return {
        "prompt_hash": prompt_hash,
        "contract_hash": contract_hash,
        "contract": contract_dict,
        "git_commit": commit,
    }


def _default_output_path() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"eval_report_{ts}.json"


def _append_eval_history(
    summary: dict[str, Any],
    report: dict[str, Any],
    report_file: str,
    history_path: str,
) -> None:
    versions = report.get("versions", {})
    entry = {
        "generated_at": report["generated_at"],
        "model": report["model"],
        "quick_mode": report["quick_mode"],
        "total_scenarios": summary["total_scenarios"],
        "trajectory_pass_rate": summary["trajectory_pass_rate"],
        "avg_judge_overall": summary.get("avg_judge_overall"),
        "report_file": report_file,
        "prompt_hash": versions.get("prompt_hash"),
        "contract_hash": versions.get("contract_hash"),
        "git_commit": versions.get("git_commit"),
    }
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Main runner ───────────────────────────────────────────────────────

def run_evaluation(
    output_path: str | None = None,
    use_judge: bool = True,
    quick: bool = False,
    eval_history_path: str = "data/observability/eval_history.jsonl",
) -> dict[str, Any]:
    resolved_path = output_path or _default_output_path()
    settings = Settings()
    agent = EnergyAdvisorAgent(settings=settings)
    scenarios = QUICK_SCENARIOS if quick else ALL_SCENARIOS

    logger.info(
        "Starting evaluation | scenarios={} judge={} model={}",
        len(scenarios),
        use_judge,
        settings.selected_model(),
    )

    results = [
        evaluate_scenario(s, agent, settings, use_judge)
        for s in scenarios
    ]

    summary = compute_summary(results)
    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model":        settings.selected_model(),
        "judge_model":  settings.model_quality if use_judge else None,
        "quick_mode":   quick,
        "versions":     artifact_versions(SYSTEM_INSTRUCTIONS, agent.contract.to_dict()),
        "summary":      summary,
        "scenarios":    results,
    }

    with open(resolved_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    _append_eval_history(summary, report, resolved_path, eval_history_path)

    logger.success("Report saved → {}", resolved_path)
    logger.success("History updated → {}", eval_history_path)
    return report


# ── CLI entrypoint ────────────────────────────────────────────────────

def _print_summary(report: dict[str, Any]) -> None:
    s = report["summary"]
    print("\n" + "=" * 60)
    print("EcoHome Evaluation Report")
    print("=" * 60)
    print(f"Generated : {report['generated_at']}")
    print(f"Model     : {report['model']}")
    print(f"Scenarios : {s['total_scenarios']}  |  Errors: {s['errors']}")
    print(f"Avg time  : {s['avg_elapsed_s']}s per scenario")
    print(f"Est. cost : ${s.get('total_estimated_cost_usd', 0):.6f} total")
    print(f"Gates     : {'PASS' if s.get('quality_gates_pass') else 'CHECK'}")
    print()
    print(f"Trajectory pass rate : {s['trajectory_pass_rate']:.0%}  "
          f"({s['trajectory_pass_count']}/{s['total_scenarios']})")

    if "avg_judge_overall" in s:
        print()
        print("LLM-as-judge scores (1–5):")
        for key in ("grounding", "completeness", "actionability", "honesty", "overall"):
            print(f"  {key:<15} {s[f'avg_judge_{key}']:.2f}")

    print()
    print("Per-scenario trajectory:")
    for r in report["scenarios"]:
        icon = "✅" if r["trajectory_pass"] else "❌"
        missing = f"  missing: {r['missing_tools']}" if r["missing_tools"] else ""
        if not r.get("order_pass", True):
            missing += "  order: out-of-sequence"
        judge_str = ""
        if r.get("judge_scores"):
            judge_str = f"  judge={r['judge_scores']['overall']:.1f}"
        print(f"  {icon} {r['scenario_id']}{missing}{judge_str}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EcoHome agent evaluation pipeline.")
    parser.add_argument(
        "--output", default=None,
        help="Path to output JSON report (default: eval_report_YYYYMMDD_HHMMSS.json)",
    )
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM-as-judge (trajectory only)")
    parser.add_argument("--quick", action="store_true", help="Run 4 scenarios instead of all 12")
    args = parser.parse_args()

    report = run_evaluation(
        output_path=args.output,
        use_judge=not args.no_judge,
        quick=args.quick,
    )
    _print_summary(report)
