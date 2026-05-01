"""Unit tests for the GuardPipeline shape."""

from __future__ import annotations

import asyncio

import pytest

from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import PipelineContractValidationError
from arc_guard_core.pipeline import GuardPipeline
from arc_guard_core.types import (
    Finding,
    GuardInput,
    PolicyDecision,
    RiskLevel,
)


def test_empty_pipeline_passes_through_text() -> None:
    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.pre_process_sync(GuardInput(text="hello"))
    assert result.action == "pass"
    assert result.text == "hello"
    assert result.is_clean
    assert result.bypass_reason is None
    assert result.phase == "pre_process"


def test_post_process_sets_phase() -> None:
    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.post_process_sync(GuardInput(text="answer"))
    assert result.phase == "post_process"


def test_disabled_returns_bypass() -> None:
    pipeline = GuardPipeline(config=GuardConfig(enabled=False))
    result = pipeline.pre_process_sync(GuardInput(text="x"))
    assert result.action == "pass"
    assert result.bypass_reason == "disabled"


def test_async_entry_points() -> None:
    pipeline = GuardPipeline(config=GuardConfig())

    async def run() -> None:
        pre = await pipeline.pre_process(GuardInput(text="a"))
        post = await pipeline.post_process(GuardInput(text="b"))
        assert pre.action == "pass"
        assert post.phase == "post_process"

    asyncio.run(run())


def test_returned_result_is_immutable() -> None:
    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.pre_process_sync(GuardInput(text="hi"))
    with pytest.raises(Exception):
        result.text = "hijacked"  # type: ignore[misc]


def test_validate_finding_rejects_invalid_span() -> None:
    bad = Finding("X", start=10, end=5, risk_level=RiskLevel.LOW, inspector="t")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        GuardPipeline.validate_findings([bad])
    assert excinfo.value.code == "pipeline.invalid_span"
    assert "start" in excinfo.value.details and "end" in excinfo.value.details


def test_validate_finding_rejects_out_of_range_score() -> None:
    bad = Finding("X", 0, 5, RiskLevel.LOW, "t", score=1.5)
    with pytest.raises(PipelineContractValidationError) as excinfo:
        GuardPipeline.validate_findings([bad])
    assert excinfo.value.code == "pipeline.invalid_score"


def test_validate_finding_rejects_missing_inspector() -> None:
    bad = Finding("X", 0, 5, RiskLevel.LOW, "")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        GuardPipeline.validate_findings([bad])
    assert excinfo.value.code == "pipeline.missing_inspector"


def test_validate_decision_rejects_empty_finding_ids() -> None:
    bad = PolicyDecision(finding_ids=(), strategy="redact", severity=RiskLevel.LOW, rationale="r")
    with pytest.raises(PipelineContractValidationError) as excinfo:
        GuardPipeline.validate_decisions([bad])
    assert excinfo.value.code == "pipeline.invalid_decision"
