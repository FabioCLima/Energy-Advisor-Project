from __future__ import annotations

from unittest.mock import MagicMock

from energy_advisor.contract import AgentContract
from energy_advisor.guardrails import GuardrailMode


def _mock_settings(mode: GuardrailMode = GuardrailMode.BLOCK) -> MagicMock:
    s = MagicMock()
    s.guardrail_mode = mode
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
