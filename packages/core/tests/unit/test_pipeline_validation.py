"""T051 — Pipeline contract validation (FR-018)."""

from __future__ import annotations

import pytest

from arc_guard_core.exceptions import PipelineContractValidationError
from arc_guard_core.pipeline import GuardPipeline, _validate_decision, _validate_finding
from arc_guard_core.types import Finding, PolicyDecision, RiskLevel


def test_finding_with_invalid_span_rejected() -> None:
    bad = Finding("EMAIL", start=10, end=5, risk_level=RiskLevel.LOW, inspector="t")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        _validate_finding(bad)
    assert excinfo.value.code == "pipeline.invalid_span"
    assert excinfo.value.details["start"] == 10
    assert excinfo.value.details["end"] == 5


def test_finding_with_negative_start_rejected() -> None:
    bad = Finding("EMAIL", start=-1, end=5, risk_level=RiskLevel.LOW, inspector="t")
    with pytest.raises(PipelineContractValidationError):
        _validate_finding(bad)


def test_finding_with_score_above_one_rejected() -> None:
    bad = Finding("EMAIL", 0, 5, RiskLevel.LOW, "t", score=1.5)
    with pytest.raises(PipelineContractValidationError) as excinfo:
        _validate_finding(bad)
    assert excinfo.value.code == "pipeline.invalid_score"


def test_finding_with_score_below_zero_rejected() -> None:
    bad = Finding("EMAIL", 0, 5, RiskLevel.LOW, "t", score=-0.1)
    with pytest.raises(PipelineContractValidationError) as excinfo:
        _validate_finding(bad)
    assert excinfo.value.code == "pipeline.invalid_score"


def test_finding_with_missing_inspector_rejected() -> None:
    bad = Finding("EMAIL", 0, 5, RiskLevel.LOW, "")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        _validate_finding(bad)
    assert excinfo.value.code == "pipeline.missing_inspector"


def test_decision_with_empty_finding_ids_rejected() -> None:
    bad = PolicyDecision(finding_ids=(), strategy="redact", severity=RiskLevel.LOW, rationale="r")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        _validate_decision(bad)
    assert excinfo.value.code == "pipeline.invalid_decision"


def test_decision_with_empty_strategy_rejected() -> None:
    bad = PolicyDecision(finding_ids=(0,), strategy="", severity=RiskLevel.LOW, rationale="r")
    with pytest.raises(PipelineContractValidationError):
        _validate_decision(bad)


def test_decision_with_empty_rationale_rejected() -> None:
    bad = PolicyDecision(finding_ids=(0,), strategy="redact", severity=RiskLevel.LOW, rationale="")
    with pytest.raises(PipelineContractValidationError):
        _validate_decision(bad)


def test_pipeline_helper_validates_lists() -> None:
    bad = [
        Finding("E", 0, 5, RiskLevel.LOW, "t"),
        Finding("E", 10, 5, RiskLevel.LOW, "t"),  # invalid span
    ]
    with pytest.raises(PipelineContractValidationError):
        GuardPipeline.validate_findings(bad)
