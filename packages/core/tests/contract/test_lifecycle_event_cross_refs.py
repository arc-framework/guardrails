"""Contract: cross-reference fields are typed `str` (not Optional) and follow
the documented v1 cross-ref catalog.
"""

from __future__ import annotations

from dataclasses import fields

from arc_guard_core.lifecycle import (
    BackendResponded,
    DecisionEmitted,
    FindingProduced,
    PayloadRewritten,
    RefusalProduced,
    SanitizationApplied,
    StrategyExecuted,
)


def _field_type(cls: type, field_name: str) -> str:
    for f in fields(cls):
        if f.name == field_name:
            return str(f.type)
    raise AssertionError(f"{cls.__name__} has no field {field_name!r}")


def test_strategy_executed_has_finding_id_field() -> None:
    assert _field_type(StrategyExecuted, "finding_id") == "str"


def test_sanitization_applied_has_finding_id_field() -> None:
    assert _field_type(SanitizationApplied, "finding_id") == "str"


def test_refusal_produced_has_decision_id_field() -> None:
    assert _field_type(RefusalProduced, "decision_id") == "str"


def test_backend_responded_has_swap_origin_id_field() -> None:
    # `str | None` because not every backend call follows a payload rewrite
    assert "str" in _field_type(BackendResponded, "swap_origin_id")


def test_decision_emitted_has_decision_id_field() -> None:
    """RefusalProduced.decision_id points at DecisionEmitted.decision_id (not .id)."""
    assert _field_type(DecisionEmitted, "decision_id") == "str"


def test_finding_produced_has_id_for_cross_ref_targets() -> None:
    """Cross-refs from StrategyExecuted/SanitizationApplied land on FindingProduced.id."""
    # Universal envelope guarantees this; just make the contract explicit.
    assert _field_type(FindingProduced, "id") == "str"


def test_payload_rewritten_has_id_for_cross_ref_targets() -> None:
    """BackendResponded.swap_origin_id lands on PayloadRewritten.id."""
    assert _field_type(PayloadRewritten, "id") == "str"
