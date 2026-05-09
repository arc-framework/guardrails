"""Jailbreak signals are converted into ``Finding`` entries on the result."""

from __future__ import annotations

import pytest
from arc_guard_core.deception import ConversationState
from arc_guard_core.jailbreak import JailbreakSignal
from arc_guard_core.types import GuardInput

from arc_guard.pipeline import GuardPipeline


class _FixedDetector:
    """Stub detector that returns a single configurable signal."""

    def __init__(self, *, category: str, confidence: float) -> None:
        self._category = category
        self._confidence = confidence

    @property
    def detector_id(self) -> str:
        return "stub-fixed:1"

    def detect(
        self,
        text: str,
        *,
        conversation_state: ConversationState | None = None,
    ) -> tuple[JailbreakSignal, ...]:
        del text, conversation_state
        return (
            JailbreakSignal(
                category=self._category,  # type: ignore[arg-type]
                confidence=self._confidence,
                evidence_reference="STUB_TOKEN",
                detector_id=self.detector_id,
            ),
        )


@pytest.mark.asyncio
async def test_signal_appears_as_finding_with_category_entity_type() -> None:
    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_FixedDetector(
            category="role_play", confidence=0.4,
        ),
    )
    result = await pipeline.pre_process(GuardInput(text="anything"))
    role_findings = [
        f for f in result.findings
        if f.entity_type == "JAILBREAK_ROLE_PLAY"
    ]
    assert len(role_findings) == 1
    assert role_findings[0].score == 0.4
    assert role_findings[0].metadata["jailbreak_category"] == "role_play"


@pytest.mark.asyncio
async def test_each_category_produces_distinct_entity_type() -> None:
    expected_pairs = [
        ("role_play", "JAILBREAK_ROLE_PLAY"),
        ("hypothetical", "JAILBREAK_HYPOTHETICAL"),
        ("policy_erosion", "JAILBREAK_POLICY_EROSION"),
        ("indirect_injection", "JAILBREAK_INDIRECT_INJECTION"),
        ("direct_override", "JAILBREAK_DIRECT_OVERRIDE"),
    ]
    for category, entity_type in expected_pairs:
        pipeline = GuardPipeline(
            inspectors=[],
            jailbreak_detector=_FixedDetector(
                category=category, confidence=0.3,
            ),
        )
        result = await pipeline.pre_process(GuardInput(text="anything"))
        assert any(f.entity_type == entity_type for f in result.findings), (
            f"category {category} did not produce entity_type {entity_type}"
        )


@pytest.mark.asyncio
async def test_no_findings_when_detector_returns_empty() -> None:
    class _NoOp:
        @property
        def detector_id(self) -> str:
            return "noop:1"

        def detect(self, text, *, conversation_state=None):
            return ()

    pipeline = GuardPipeline(
        inspectors=[],
        jailbreak_detector=_NoOp(),
    )
    result = await pipeline.pre_process(GuardInput(text="benign"))
    jb_findings = [
        f for f in result.findings
        if f.entity_type.startswith("JAILBREAK_")
    ]
    assert jb_findings == []
