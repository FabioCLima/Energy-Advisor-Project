from __future__ import annotations

from unittest.mock import MagicMock

from energy_advisor.contract import AgentContract
from energy_advisor.guardrails import GuardrailMode


def _mock_settings(
    mode: GuardrailMode = GuardrailMode.BLOCK,
    scope_mode: GuardrailMode = GuardrailMode.AUDIT,
) -> MagicMock:
    s = MagicMock()
    s.guardrail_mode = mode
    s.scope_mode = scope_mode
    return s


def test_from_settings_sets_persona() -> None:
    contract = AgentContract.from_settings(_mock_settings())

    assert contract.persona == "EcoHome Energy Advisor"


def test_from_settings_inherits_enforcement_mode_from_settings() -> None:
    contract = AgentContract.from_settings(_mock_settings(GuardrailMode.AUDIT))

    assert contract.enforcement_mode == GuardrailMode.AUDIT


def test_from_settings_block_mode_is_default() -> None:
    contract = AgentContract.from_settings(_mock_settings(GuardrailMode.BLOCK))

    assert contract.enforcement_mode == GuardrailMode.BLOCK


def test_from_settings_allowed_topics_is_non_empty() -> None:
    contract = AgentContract.from_settings(_mock_settings())

    assert len(contract.allowed_topics) > 0
    assert "energy consumption" in contract.allowed_topics
    assert "EV charging" in contract.allowed_topics


def test_to_dict_is_json_serialisable() -> None:
    import json

    contract = AgentContract.from_settings(_mock_settings())
    d = contract.to_dict()

    # Should not raise
    serialised = json.dumps(d)
    assert "EcoHome Energy Advisor" in serialised
    assert "block" in serialised


def test_to_dict_enforcement_mode_is_string_value() -> None:
    contract = AgentContract.from_settings(_mock_settings(GuardrailMode.AUDIT))
    d = contract.to_dict()

    assert d["enforcement_mode"] == "audit"


def test_contract_can_be_passed_directly() -> None:
    custom = AgentContract(
        scope="custom scope",
        allowed_topics=["solar"],
        persona="CustomBot",
        enforcement_mode=GuardrailMode.AUDIT,
    )

    assert custom.enforcement_mode == GuardrailMode.AUDIT
    assert custom.persona == "CustomBot"


# ── E-2: topicality enforcement ───────────────────────────────────────

import pytest  # noqa: E402

from energy_advisor.evaluation.scenarios import ALL_SCENARIOS  # noqa: E402

_CONTRACT = AgentContract.from_settings(_mock_settings())


@pytest.mark.parametrize("question", [
    "Me recomende ações da bolsa para investir",
    "Qual a receita de bolo de cenoura?",
    "Quem ganhou o jogo do Corinthians ontem?",
    "Write me a poem about the ocean",
])
def test_check_scope_flags_out_of_scope_questions(question: str) -> None:
    result = _CONTRACT.check_scope(question)

    assert result.passed is False
    assert result.severity is not None


@pytest.mark.parametrize(
    "question",
    [s.question for s in ALL_SCENARIOS],
    ids=[s.id for s in ALL_SCENARIOS],
)
def test_check_scope_passes_every_eval_scenario_question(question: str) -> None:
    # Zero false positives on the questions the product is evaluated against.
    assert _CONTRACT.check_scope(question).passed is True


def test_check_scope_is_accent_insensitive() -> None:
    assert _CONTRACT.check_scope("qual a irradiância solar agora?").passed is True
    assert _CONTRACT.check_scope("qual a IRRADIANCIA solar agora?").passed is True


def test_to_dict_includes_scope_mode_and_keywords() -> None:
    d = AgentContract.from_settings(_mock_settings()).to_dict()

    assert d["scope_mode"] == "audit"
    assert isinstance(d["topic_keywords"], list)
    assert "energia" in d["topic_keywords"]
