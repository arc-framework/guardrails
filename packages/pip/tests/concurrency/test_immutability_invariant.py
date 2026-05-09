"""Pydantic / dataclass contract objects are immutable after construction.

The frozen-instance guarantee is what makes these objects safe to share
across concurrent runs without locking. Every type listed in the
spec's immutability requirement is checked here so a future field
addition that flips a model from ``frozen=True`` to mutable fails this
test before regressing the concurrency contract.
"""

from __future__ import annotations

import dataclasses

import pytest
from arc_guard_core.decision import DecisionRecord, FindingSummary
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.types import (
    ClarificationRequest,
    Finding,
    GuardContext,
    GuardInput,
    GuardResult,
    PolicyDecision,
    RefusalEnvelope,
    RiskLevel,
)
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError


def _build_finding() -> Finding:
    return Finding(
        entity_type="EMAIL",
        start=0,
        end=5,
        risk_level=RiskLevel.LOW,
        inspector="stub",
    )


def _build_guard_input() -> GuardInput:
    return GuardInput(text="hello", context=GuardContext(correlation_id="c1"))


def _build_guard_result() -> GuardResult:
    return GuardResult(
        text="hello",
        action="pass",
        findings=(_build_finding(),),
        bypass_reason=None,
        phase="pre_process",
    )


def _build_policy_decision() -> PolicyDecision:
    return PolicyDecision(
        finding_ids=(0,),
        strategy="redact",
        severity=RiskLevel.LOW,
        rationale="stub",
    )


def _build_refusal_envelope() -> RefusalEnvelope:
    return RefusalEnvelope(
        code="strategy_failed",
        trigger="StrategyError",
        policy="internal-failure",
        human_message="blocked",
        next_steps=("retry",),
    )


def _build_clarification_request() -> ClarificationRequest:
    return ClarificationRequest(
        suggested_rephrase="please rephrase",
        next_steps=("rephrase the question",),
    )


def _build_decision_record() -> DecisionRecord:
    from arc_guard_core.policy import RiskBand

    return DecisionRecord(
        correlation_id="c1",
        phase="pre_process",
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
        findings=(),
        transforms=(),
        fired_rules=(),
        refusal_code=None,
        clarification_present=False,
        latency_ms=1.0,
    )


def _build_observability_config() -> ObservabilityConfig:
    return ObservabilityConfig()


IMMUTABLE_TYPES = [
    ("GuardInput", _build_guard_input, "text", "mutated"),
    ("GuardResult", _build_guard_result, "text", "mutated"),
    ("Finding", _build_finding, "inspector", "mutated"),
    ("PolicyDecision", _build_policy_decision, "rationale", "mutated"),
    ("RefusalEnvelope", _build_refusal_envelope, "human_message", "mutated"),
    ("ClarificationRequest", _build_clarification_request, "suggested_rephrase", "x"),
    ("DecisionRecord", _build_decision_record, "aggregate_action", "mutated"),
    ("ObservabilityConfig", _build_observability_config, "sampling_rate", 0.5),
]


@pytest.mark.parametrize("name, builder, attr, value", IMMUTABLE_TYPES, ids=lambda v: v if isinstance(v, str) else "")
def test_instance_is_frozen(name: str, builder, attr: str, value) -> None:  # type: ignore[no-untyped-def]
    instance = builder()
    is_pydantic = isinstance(instance, BaseModel)
    is_dataclass = dataclasses.is_dataclass(instance) and not isinstance(instance, type)
    assert is_pydantic or is_dataclass, f"{name} is neither pydantic nor dataclass"

    with pytest.raises((PydanticValidationError, dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        setattr(instance, attr, value)


def test_finding_summary_is_frozen() -> None:
    summary = FindingSummary(
        entity_type="EMAIL",
        start=0,
        end=5,
        length=5,
        risk_level=RiskLevel.LOW,
        inspector="stub",
    )
    with pytest.raises(
        (PydanticValidationError, dataclasses.FrozenInstanceError, TypeError, AttributeError)
    ):
        summary.length = 6  # type: ignore[misc]
