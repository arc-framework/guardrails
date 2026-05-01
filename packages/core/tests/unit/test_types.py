"""Unit tests for arc_guard_core.types."""

from __future__ import annotations

import pytest

from arc_guard_core.types import (
    EntityDefinition,
    Finding,
    GuardContext,
    GuardInput,
    GuardResult,
    PolicyDecision,
    RefusalEnvelope,
    RiskLevel,
)


def test_risk_level_ordering() -> None:
    assert RiskLevel.NONE < RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH < RiskLevel.CRITICAL


def test_guard_context_default() -> None:
    ctx = GuardContext()
    assert ctx.source == "input"
    assert ctx.user_id is None
    assert ctx.correlation_id is None
    assert ctx.metadata == {}


def test_guard_context_with_correlation_id() -> None:
    ctx = GuardContext(correlation_id="trace-123", source="output")
    assert ctx.correlation_id == "trace-123"
    assert ctx.source == "output"


def test_guard_input_default_policy_hints_is_empty_frozenset() -> None:
    gi = GuardInput(text="hi")
    assert isinstance(gi.policy_hints, frozenset)
    assert len(gi.policy_hints) == 0


def test_guard_input_with_hints() -> None:
    gi = GuardInput(text="hi", policy_hints=frozenset({"strict"}))
    assert "strict" in gi.policy_hints


def test_finding_span_property() -> None:
    f = Finding(
        entity_type="EMAIL",
        start=10,
        end=20,
        risk_level=RiskLevel.LOW,
        inspector="presidio",
    )
    assert f.span == "[10:20]"


def test_guard_result_is_clean_and_max_risk() -> None:
    empty = GuardResult(text="x")
    assert empty.is_clean
    assert empty.max_risk == RiskLevel.NONE

    populated = GuardResult(
        text="x",
        findings=(
            Finding("EMAIL", 0, 5, RiskLevel.LOW, "presidio"),
            Finding("PHONE", 10, 15, RiskLevel.HIGH, "presidio"),
        ),
    )
    assert not populated.is_clean
    assert populated.max_risk == RiskLevel.HIGH


def test_policy_decision_construction() -> None:
    pd = PolicyDecision(
        finding_ids=(0,),
        strategy="redact",
        severity=RiskLevel.LOW,
        rationale="email is low risk",
    )
    assert pd.strategy == "redact"


def test_refusal_envelope_construction() -> None:
    env = RefusalEnvelope(
        code="jailbreak",
        trigger="role-play",
        policy="default",
        human_message="This request was blocked.",
    )
    assert env.decisions == ()
    assert env.next_steps == ()


def test_entity_definition_optional_fields() -> None:
    e = EntityDefinition(name="X", category="CUSTOM")
    assert e.pattern is None
    assert e.recognizer is None


def test_types_are_frozen() -> None:
    f = Finding("EMAIL", 0, 5, RiskLevel.LOW, "p")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        f.start = 99  # type: ignore[misc]
