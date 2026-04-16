"""Tests for energy_advisor.config.Settings."""
from __future__ import annotations

import pytest
from energy_advisor.config import Settings


def test_default_model_preset():
    """Default preset resolves to fast, model to gpt-4o-mini."""
    s = Settings()
    assert s.model_preset == "fast"
    assert s.selected_model() == "gpt-4o-mini"


def test_quality_preset(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL_PRESET", "quality")
    s = Settings()
    assert s.selected_model() == "gpt-4o"


def test_custom_preset_requires_model(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL_PRESET", "custom")
    monkeypatch.delenv("ENERGY_ADVISOR_MODEL", raising=False)
    s = Settings()
    with pytest.raises(ValueError, match="ENERGY_ADVISOR_MODEL must be set"):
        s.selected_model()


def test_custom_preset_with_model(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL_PRESET", "custom")
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL", "gpt-3.5-turbo")
    s = Settings()
    assert s.selected_model() == "gpt-3.5-turbo"


def test_invalid_preset_raises(monkeypatch):
    monkeypatch.setenv("ENERGY_ADVISOR_MODEL_PRESET", "turbo")
    with pytest.raises(ValueError):
        Settings()


def test_api_key_priority(monkeypatch):
    """ENERGY_ADVISOR_API_KEY takes precedence over OPENAI_API_KEY."""
    monkeypatch.setenv("ENERGY_ADVISOR_API_KEY", "explicit-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    s = Settings()
    assert s.selected_api_key() == "explicit-key"


def test_api_key_fallback(monkeypatch):
    monkeypatch.delenv("ENERGY_ADVISOR_API_KEY", raising=False)
    monkeypatch.delenv("VOCAREUM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    s = Settings()
    assert s.selected_api_key() == "openai-key"


def test_default_paths():
    s = Settings()
    assert s.db_path == "data/energy_data.db"
    assert s.documents_dir == "data/documents"
    assert s.vectorstore_dir == "data/vectorstore"
