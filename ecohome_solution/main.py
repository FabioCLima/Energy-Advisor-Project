from __future__ import annotations

import argparse

from energy_advisor import EnergyAdvisorAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="EcoHome Energy Advisor (CLI)")
    parser.add_argument("question", help="User question to the Energy Advisor")
    parser.add_argument("--context", default=None, help="Optional extra context")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full LangGraph result dict (debugging). Default prints only the final answer.",
    )
    args = parser.parse_args()

    agent = EnergyAdvisorAgent()
    result = agent.invoke(args.question, context=args.context)
    if args.json:
        print(result)
    else:
        messages = result.get("messages", [])
        answer = messages[-1].content if messages else ""
        print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
