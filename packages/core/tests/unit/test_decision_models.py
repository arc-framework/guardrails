"""Decision-record model unit tests."""

from __future__ import annotations

import dataclasses
import json

from arc_guard_core.decision import DecisionRecord, FindingSummary
from arc_guard_core.policy import RiskBand, TransformSummary
from arc_guard_core.types import RiskLevel


def test_finding_summary_fields() -> None:
    fs = FindingSummary(
        entity_type="EMAIL_ADDRESS",
        start=10,
        end=25,
        length=15,
        risk_level=RiskLevel.LOW,
        inspector="presidio",
    )
    assert fs.score is None


def test_decision_record_json_roundtrip() -> None:
    rec = DecisionRecord(
        correlation_id="trace-1",
        phase="pre_process",
        aggregate_action="redact",
        aggregate_band=RiskBand.LOW,
        findings=(
            FindingSummary(
                entity_type="EMAIL_ADDRESS",
                start=0,
                end=10,
                length=10,
                risk_level=RiskLevel.LOW,
                inspector="presidio",
            ),
        ),
        transforms=(
            TransformSummary(
                strategy="redact",
                target_finding_index=0,
                before_length=10,
                after_length=15,
                replacement_kind="placeholder",
            ),
        ),
        fired_rules=("r1",),
        refusal_code=None,
        clarification_present=False,
        latency_ms=0.5,
    )
    payload = dataclasses.asdict(rec)
    serialized = json.dumps(payload, default=str)
    parsed = json.loads(serialized)
    assert parsed["correlation_id"] == "trace-1"
    assert parsed["phase"] == "pre_process"
    assert parsed["aggregate_band"] == "low"
    assert parsed["findings"][0]["entity_type"] == "EMAIL_ADDRESS"
    assert parsed["transforms"][0]["replacement_kind"] == "placeholder"


def test_decision_record_metadata_default_empty() -> None:
    rec = DecisionRecord(
        correlation_id=None,
        phase="post_process",
        aggregate_action="pass",
        aggregate_band=RiskBand.LOW,
        findings=(),
        transforms=(),
        fired_rules=(),
        refusal_code=None,
        clarification_present=False,
        latency_ms=0.0,
    )
    assert rec.metadata == {}
