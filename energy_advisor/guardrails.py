"""Deterministic safety guardrails for the EcoHome assistant."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Violation severity used for proportional auditing and alerting."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardrailViolation(ValueError):
    """Raised when a request or response violates a product safety rule."""


@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    reason: str | None = None
    severity: Severity | None = None


_INJECTION_PATTERNS = (
    re.compile(r"ignore (all )?(previous|prior|system) instructions", re.IGNORECASE),
    re.compile(r"reveal (the )?(system prompt|developer message|hidden instructions)", re.IGNORECASE),
    re.compile(r"print (the )?(env|environment variables|secrets|api key)", re.IGNORECASE),
    re.compile(r"bypass (safety|guardrails|policy)", re.IGNORECASE),
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|LANGCHAIN_API_KEY)\s*="),
)

# Brazilian PII — input presence is audited (MEDIUM, not blocked);
# reproduction in model output is blocked (HIGH).
_PII_PATTERNS = (
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),           # CPF
    re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),     # CNPJ
    re.compile(r"\(\d{2}\)\s*\d{4,5}[-\s]\d{4}"),            # phone (DDD) 9xxxx-xxxx
    re.compile(r"\+55\s?\d{2}\s?\d{4,5}[-\s]?\d{4}"),        # phone +55 11 9xxxx-xxxx
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),  # e-mail
)


def validate_user_input(question: str, *, max_chars: int = 2000) -> GuardrailResult:
    cleaned = (question or "").strip()
    if not cleaned:
        return GuardrailResult(False, "Question cannot be empty.", Severity.LOW)
    if len(cleaned) > max_chars:
        return GuardrailResult(False, f"Question exceeds the {max_chars} character limit.", Severity.LOW)
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            return GuardrailResult(False, "Request looks like prompt injection or secret exfiltration.", Severity.CRITICAL)
    for pattern in _PII_PATTERNS:
        if pattern.search(cleaned):
            # User may legitimately reference their own data; audit but do not block.
            return GuardrailResult(True, "Input contains PII (CPF/CNPJ/phone/e-mail). Logged for audit.", Severity.MEDIUM)
    return GuardrailResult(True)


def validate_model_output(answer: str) -> GuardrailResult:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(answer or ""):
            return GuardrailResult(False, "Response appears to contain a secret or credential.", Severity.CRITICAL)
    for pattern in _PII_PATTERNS:
        if pattern.search(answer or ""):
            return GuardrailResult(False, "Response reproduces PII (CPF/CNPJ/phone/e-mail).", Severity.HIGH)
    return GuardrailResult(True)


def ensure_safe_user_input(question: str, *, max_chars: int = 2000) -> None:
    result = validate_user_input(question, max_chars=max_chars)
    if not result.passed:
        raise GuardrailViolation(result.reason or "Unsafe input rejected.")


def ensure_safe_model_output(answer: str) -> None:
    result = validate_model_output(answer)
    if not result.passed:
        raise GuardrailViolation(result.reason or "Unsafe output rejected.")
