"""AgentContract — explicit, auditable scope definition for the EcoHome agent.

The SYSTEM_INSTRUCTIONS string in prompts.py continues to drive the LLM
behaviour. This module extracts the metadata that was previously implicit
in that string into a structured, inspectable object — and enforces it:
`check_scope` is a deterministic topicality check, run on the first turn of
a conversation under the same AUDIT/BLOCK rollout pattern as the guardrails.

Benefits:
- The contract can be serialised and versioned alongside the model
  (topic keywords included — changing them changes the contract_hash).
- Enforcement policy is declared here instead of being read directly from
  Settings inside each call site.
- Tests can swap the contract to assert behaviour under different modes.

Scope-check design note: keyword matching is a product guardrail, not a
security one — it measures topicality cheaply and deterministically. Greetings
and smalltalk have no energy keyword and will be flagged; in AUDIT (default)
that only logs, and in BLOCK the redirect message is friendly by design.
The documented evolution is a lightweight classifier.
"""
from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from .guardrails import GuardrailMode, GuardrailResult, Severity

if TYPE_CHECKING:
    from .config import Settings


def _normalize(text: str) -> str:
    """Casefold and strip accents so 'Irradiância' matches 'irradiancia'."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Stored unaccented/lowercase; matched against _normalize(question).
DEFAULT_TOPIC_KEYWORDS: tuple[str, ...] = (
    # PT — domínio de energia residencial
    "energia", "eletrica", "eletricidade", "luz", "conta",
    "consumo", "consumi", "gasto", "gastei", "custo", "custou", "custaria",
    "tarifa", "bandeira", "kwh", "watt",
    "economia", "economizar", "economizaria", "poupar",
    "solar", "painel", "geracao", "irradiancia",
    "carregar", "carregamento", "bateria", "tesla", "carro eletrico",
    "ar-condicionado", "ar condicionado", "chuveiro", "geladeira",
    "lava-louca", "lava-roupa", "maquina de lavar",
    "dispositivo", "aparelho", "eletrodomestico",
    "home office", "escritorio",
    "horario de ponta", "fora de ponta", "pico",
    "previsao", "clima", "tempo amanha",
    "enel", "aneel", "distribuidora",
    # EN — same domain
    "energy", "electricity", "power", "consumption", "usage",
    "tariff", "rate", "bill", "savings", "cost",
    "panel", "charge", "charging", "battery", "ev",
    "device", "appliance", "weather", "forecast",
    "peak", "off-peak",
)


@dataclass(frozen=True)
class AgentContract:
    """Structured scope and enforcement policy for one agent deployment."""

    scope: str
    allowed_topics: list[str]
    persona: str
    enforcement_mode: GuardrailMode = GuardrailMode.BLOCK
    # Topicality rollout: AUDIT logs out-of-scope questions (measure first),
    # BLOCK answers them with a redirect instead of invoking tools/LLM context.
    scope_mode: GuardrailMode = GuardrailMode.AUDIT
    topic_keywords: tuple[str, ...] = field(default=DEFAULT_TOPIC_KEYWORDS)

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
            scope_mode=settings.scope_mode,
        )

    def check_scope(self, question: str) -> GuardrailResult:
        """Deterministic topicality check against the contract's keyword set.

        Returns passed=False (Severity.LOW) when no energy-domain keyword is
        present. LOW because this is product scope, not a safety violation.
        """
        text = _normalize(question or "")
        if any(keyword in text for keyword in self.topic_keywords):
            return GuardrailResult(True)
        return GuardrailResult(
            False,
            "Question appears outside the energy-advisor scope.",
            Severity.LOW,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for auditing."""
        d = asdict(self)
        d["enforcement_mode"] = self.enforcement_mode.value
        d["scope_mode"] = self.scope_mode.value
        d["topic_keywords"] = list(self.topic_keywords)
        return d
