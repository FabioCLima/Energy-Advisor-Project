"""Evaluation runner for the EcoHome Energy Advisor agent.

Usage:
    python -m energy_advisor.evaluation.runner --output eval_report.json
    python -m energy_advisor.evaluation.runner --output eval_report.json --no-judge
    python -m energy_advisor.evaluation.runner --output eval_report.json --quick
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from ..agent import EnergyAdvisorAgent
from ..config import Settings
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

    missing_tools = [t for t in scenario.required_tools if t not in called_tools]
    trajectory_pass = len(missing_tools) == 0

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
        "called_tools":    called_tools,
        "trajectory_pass": trajectory_pass,
        "missing_tools":   missing_tools,
        "final_answer":    final_answer,
        "elapsed_s":       elapsed,
        "error":           error,
        "judge_scores":    judge_scores,
    }


# ── Summary computation ───────────────────────────────────────────────

def compute_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    traj_pass = sum(1 for r in results if r["trajectory_pass"])
    scored = [r["judge_scores"] for r in results if r.get("judge_scores")]

    summary: dict[str, Any] = {
        "total_scenarios":        total,
        "trajectory_pass_count":  traj_pass,
        "trajectory_pass_rate":   round(traj_pass / total, 2) if total else 0,
        "errors":                 sum(1 for r in results if r["error"]),
        "avg_elapsed_s":          round(sum(r["elapsed_s"] for r in results) / total, 2) if total else 0,
    }

    if scored:
        for key in ("grounding", "completeness", "actionability", "honesty", "overall"):
            summary[f"avg_judge_{key}"] = round(
                sum(s[key] for s in scored) / len(scored), 2
            )

    return summary


# ── Main runner ───────────────────────────────────────────────────────

def run_evaluation(
    output_path: str,
    use_judge: bool = True,
    quick: bool = False,
) -> dict[str, Any]:
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

    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model":        settings.selected_model(),
        "judge_model":  settings.model_quality if use_judge else None,
        "quick_mode":   quick,
        "summary":      compute_summary(results),
        "scenarios":    results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.success("Report saved → {}", output_path)
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
        judge_str = ""
        if r.get("judge_scores"):
            judge_str = f"  judge={r['judge_scores']['overall']:.1f}"
        print(f"  {icon} {r['scenario_id']}{missing}{judge_str}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EcoHome agent evaluation pipeline.")
    parser.add_argument("--output", default="eval_report.json", help="Path to output JSON report")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM-as-judge (trajectory only)")
    parser.add_argument("--quick", action="store_true", help="Run 4 scenarios instead of all 12")
    args = parser.parse_args()

    report = run_evaluation(
        output_path=args.output,
        use_judge=not args.no_judge,
        quick=args.quick,
    )
    _print_summary(report)
