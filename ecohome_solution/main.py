from __future__ import annotations

import argparse

from energy_advisor import EnergyAdvisorAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="EcoHome Energy Advisor (CLI)")
    parser.add_argument("question", help="User question to the Energy Advisor")
    parser.add_argument("--context", default=None, help="Optional extra context")
    args = parser.parse_args()

    agent = EnergyAdvisorAgent()
    result = agent.invoke(args.question, context=args.context)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

