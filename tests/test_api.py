"""API boundary tests — auth, rate limit, sanitized errors, budget mapping.

The agent is replaced by a stub, so these tests exercise only the HTTP
boundary: the four non-negotiables of turning an agent into a service.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from energy_advisor.guardrails import GuardrailViolation
from energy_advisor.observability import BudgetExceeded


class StubAgent:
    def __init__(self, behavior=None):
        self.behavior = behavior

    def invoke(self, question, context=None, config=None):
        if self.behavior:
            raise self.behavior
        from langchain_core.messages import AIMessage

        return {"messages": [AIMessage(content="stub answer")]}

    def stream(self, question, context=None, config=None):
        if self.behavior:
            raise self.behavior
        yield "stub "
        yield "chunk"


@pytest.fixture()
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("ENERGY_ADVISOR_BOOTSTRAP_ON_START", "false")
    monkeypatch.setenv("ENERGY_ADVISOR_OBSERVABILITY_TRACE_PATH", str(tmp_path / "t.jsonl"))
    monkeypatch.delenv("ENERGY_ADVISOR_API_AUTH_KEY", raising=False)
    monkeypatch.delenv("ENERGY_ADVISOR_RATE_LIMIT_PER_MINUTE", raising=False)
    # `import energy_advisor.api.app as m` would resolve to the FastAPI `app`
    # attribute re-exported by the package __init__, not the module.
    app_module = importlib.import_module("energy_advisor.api.app")
    module = importlib.reload(app_module)
    module._agent = StubAgent()
    return module


def test_health_is_public(api):
    client = TestClient(api.app)
    assert client.get("/health").json() == {"status": "ok"}


def test_invoke_returns_answer(api):
    client = TestClient(api.app)
    resp = client.post("/advisor/invoke", json={"question": "Qual a tarifa?"})

    assert resp.status_code == 200
    assert resp.json()["answer"] == "stub answer"


def test_invoke_maps_guardrail_violation_to_400(api):
    api._agent = StubAgent(behavior=GuardrailViolation("unsafe input"))
    client = TestClient(api.app)

    resp = client.post("/advisor/invoke", json={"question": "x"})

    assert resp.status_code == 400
    assert "unsafe input" in resp.json()["detail"]


def test_invoke_maps_budget_exceeded_to_429(api):
    api._agent = StubAgent(behavior=BudgetExceeded("budget blown"))
    client = TestClient(api.app)

    resp = client.post("/advisor/invoke", json={"question": "x"})

    assert resp.status_code == 429
    assert "budget blown" in resp.json()["detail"]


def test_invoke_500_does_not_leak_internals(api):
    api._agent = StubAgent(behavior=RuntimeError("secret stack detail"))
    client = TestClient(api.app)

    resp = client.post("/advisor/invoke", json={"question": "x"})

    assert resp.status_code == 500
    assert "secret stack detail" not in resp.json()["detail"]
    assert "request_id=" in resp.json()["detail"]


def test_auth_required_when_key_configured(api):
    api.settings.api_auth_key = "s3cret"
    client = TestClient(api.app)
    try:
        denied = client.post("/advisor/invoke", json={"question": "x"})
        allowed = client.post(
            "/advisor/invoke", json={"question": "x"}, headers={"X-API-Key": "s3cret"}
        )
    finally:
        api.settings.api_auth_key = None

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_rate_limit_returns_429(api):
    api.settings.rate_limit_per_minute = 2
    client = TestClient(api.app)
    try:
        first = client.post("/advisor/invoke", json={"question": "x"})
        second = client.post("/advisor/invoke", json={"question": "x"})
        third = client.post("/advisor/invoke", json={"question": "x"})
    finally:
        api.settings.rate_limit_per_minute = 0
        api._rate_windows.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_stream_emits_chunks_and_done(api):
    client = TestClient(api.app)

    resp = client.post("/advisor/stream", json={"question": "x"})

    body = resp.text
    assert resp.status_code == 200
    assert 'data: {"text": "stub "}' in body
    assert body.rstrip().endswith("data: [DONE]")


def test_stream_emits_429_payload_on_budget(api):
    api._agent = StubAgent(behavior=BudgetExceeded("budget blown"))
    client = TestClient(api.app)

    body = client.post("/advisor/stream", json={"question": "x"}).text

    assert '"status_code": 429' in body
    assert "data: [DONE]" in body
