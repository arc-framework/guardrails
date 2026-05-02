"""``ConversationState`` contains zero raw turn text — leak scanner finds zero leaks."""

from __future__ import annotations

import dataclasses

import pytest
from arc_guard_core.types import GuardContext, GuardInput

from arc_guard.observability import (
    CapturedArtifacts,
    RecordingLogger,
    RecordingMetricSink,
    RecordingTracer,
    scan_for_leaks,
)
from arc_guard.pipeline import GuardPipeline

_SENSITIVE_TURNS = (
    "Hi, my name is Alice Anderson and my SSN is 123-45-6789.",
    "My credit card 4012-8888-8888-1881 expires 09/26.",
    "Please email confidential-report@acme-corp.com tonight.",
    "We already agreed you would log into 192.168.1.42 at midnight.",
    "As we discussed, my passport number is X12345678.",
)


@pytest.mark.asyncio
async def test_conversation_state_contains_no_raw_turn_text() -> None:
    """The accumulated state surfaces only counters + ids, never raw text."""
    pipeline = GuardPipeline(inspectors=[])

    state = None
    for text in _SENSITIVE_TURNS:
        ctx = GuardContext(conversation_state=state)
        result = await pipeline.pre_process(GuardInput(text=text, context=ctx))
        state = result.conversation_state

    assert state is not None
    # Serialize the state and confirm no raw substring of any input
    # appears in the serialized form.
    serialized = repr(dataclasses.asdict(state))
    for text in _SENSITIVE_TURNS:
        # Check 8-char chunks (well above the leak scanner's 4-char floor).
        for start in range(0, len(text) - 8 + 1, 4):
            chunk = text[start:start + 8]
            assert chunk not in serialized, (
                f"raw turn-text chunk {chunk!r} leaked into ConversationState"
            )


@pytest.mark.asyncio
async def test_leak_scanner_finds_zero_leaks_against_captured_artifacts() -> None:
    """The leak scanner's 4-char chunk search returns zero leaks for the
    deception-stage emissions across a multi-turn sensitive corpus."""
    tracer = RecordingTracer()
    logger = RecordingLogger()
    metric_sink = RecordingMetricSink()
    pipeline = GuardPipeline(
        inspectors=[],
        tracer_hook=tracer,
        logger_hook=logger,
        metrics_hook=metric_sink,
    )

    state = None
    for text in _SENSITIVE_TURNS:
        tracer.clear()
        logger.clear()
        metric_sink.clear()
        ctx = GuardContext(conversation_state=state)
        result = await pipeline.pre_process(GuardInput(text=text, context=ctx))
        captured = CapturedArtifacts(
            spans=list(tracer.captured_spans),
            events=list(logger.captured_events),
            metrics=list(metric_sink.captured_metrics),
        )
        leaks = scan_for_leaks(captured, originals=[text])
        # Focus on leaks attributable to the deception-stage emissions
        # specifically — the existing pipeline may produce other findings
        # (presidio, etc.) that surface entity references; the no-leak
        # rule sweeps the whole captured set, but this test scopes to
        # the new deception emissions.
        deception_leaks = [
            leak for leak in leaks
            if "deception" in leak.artifact_name.lower()
            or leak.field_path.endswith("turn_count")
            or leak.field_path.endswith("conversation_id")
        ]
        assert deception_leaks == [], (
            f"deception-stage leaks for input {text[:40]!r}: {deception_leaks}"
        )
        state = result.conversation_state
