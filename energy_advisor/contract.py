"""AgentContract — explicit, auditable scope definition for the EcoHome agent.

The SYSTEM_INSTRUCTIONS string in prompts.py continues to drive the LLM
behaviour. This module extracts the metadata that was previously implicit
in that string into a structured, inspectable object.

Benefits:
- The contract can be serialised and versioned alongside the model.
- GuardrailMode is declared here instead of being read directly from
  Settings inside each guardrail call, making enforcement policy visible.
- Tests can swap the contract to assert behaviour under different modes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from .guardrails import GuardrailMode

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class AgentContract:
    """Structured scope and enforcement policy for one agent deployment."""

    scope: str
    allowed_topics: list[str]
    persona: str
    enforcement_mode: GuardrailMode = GuardrailMode.BLOCK

    @classmethod
    def from_settings(cls, settings: Settings) -> AgentContract:
        """Build the default EcoHome contract from runtime settings."""
        return cls(
            scope=(
                "AI energy advisor for Brazilian households. "
                "Provides data-grounded recommendations on consumption, "
                "solar generation, EV charging, electricity rates, and savings."
            ),
            allowed_topics=[
                "energy consumption",
                "solar generation",
                "EV charging",
                "electricity rates",
                "energy savings",
                "load scheduling",
                "home office energy costs",
                "weather and solar forecasting",
            ],
            persona="EcoHome Energy Advisor",
            enforcement_mode=settings.guardrail_mode,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for auditing."""
        d = asdict(self)
        d["enforcement_mode"] = self.enforcement_mode.value
        return d
