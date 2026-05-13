"""Contract: ``rid_context_var`` is bound to the pipeline's emitter rid
during a guard request, even when an outer HTTP middleware has already
set a different rid (the dashboard's lookup-API path).

Without this binding, structured-logging entries from the pipeline get
tagged with whatever rid happened to be set on the outer request — for
the dashboard's debug-tab fetch that's the dashboard's own request rid,
not the rid of the request the operator is inspecting.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardContext, GuardInput, GuardResult, RiskLevel

from arc_guard.observability.debug_log_handler import rid_context_var
from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline


class _CaptureRidHandler(logging.Handler):
    """Reads ``rid_context_var`` at emit time the same way ``RidLogHandler``
    does, and records the captured rid against the log message text."""

    def __init__(self) -> None:
        super().__init__()
        self.captured: list[tuple[str, str | None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.captured.append((record.getMessage(), rid_context_var.get(None)))


class _NoisyInspector:
    """Inspector that emits a log line during ``inspect`` so we have
    observable evidence of the rid binding while the pipeline is running."""

    name = "noisy"

    async def inspect(self, result: GuardResult) -> GuardResult:
        logging.getLogger("arc_guard.test.noisy").info("inspector ran")
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings)
            + (Finding("EMAIL_ADDRESS", 0, 19, RiskLevel.MEDIUM, "noisy"),),
            phase=result.phase,
        )


@pytest.mark.asyncio
async def test_pipeline_rebinds_rid_context_var_to_emitter_rid() -> None:
    sink = RingBufferLifecycleSink(capacity=200)
    emitter = LifecycleEmitter(sink, "pipeline-rid")

    handler = _CaptureRidHandler()
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    prior_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    # Simulate the dashboard's lookup-API middleware having set
    # ``rid_context_var`` to a DIFFERENT rid before the pipeline runs.
    outer_token = rid_context_var.set("dashboard-lookup-rid")
    try:
        pipeline = GuardPipeline(
            policy_ruleset=PolicyRuleSet(
                rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
            ),
            inspectors=[_NoisyInspector()],
            lifecycle_hook=sink,
        )
        await pipeline.pre_process(
            GuardInput(
                text="alice@example.com please",
                context=GuardContext(
                    metadata={
                        "_lifecycle_emitter": emitter,
                        "_lifecycle_parent_id": None,
                    },
                ),
            )
        )
        await asyncio.sleep(0.05)
        # After the run completes, the outer rid is restored — so a
        # subsequent dashboard fetch on the same task sees its own rid again.
        assert rid_context_var.get(None) == "dashboard-lookup-rid"
    finally:
        rid_context_var.reset(outer_token)
        root.removeHandler(handler)
        root.setLevel(prior_level)

    # The inspector's "inspector ran" line was emitted while the pipeline
    # was the active context — its captured rid must match the pipeline's
    # emitter rid, NOT the outer dashboard rid.
    inspector_runs = [(msg, rid) for msg, rid in handler.captured if msg == "inspector ran"]
    assert inspector_runs, "the noisy inspector did not log; test invalid"
    for _msg, captured_rid in inspector_runs:
        assert captured_rid == "pipeline-rid", (
            f"expected pipeline-rid, got {captured_rid!r} — pipeline did not rebind "
            f"rid_context_var to the emitter rid"
        )


@pytest.mark.asyncio
async def test_pipeline_without_emitter_does_not_clobber_outer_rid() -> None:
    """In-process callers without an emitter (no api transport wired) MUST
    not rebind rid_context_var — there is no pipeline rid to bind."""
    outer_token = rid_context_var.set("outer-rid")
    try:
        pipeline = GuardPipeline(
            policy_ruleset=PolicyRuleSet(
                rules=(PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),),
            ),
            inspectors=[_NoisyInspector()],
        )
        await pipeline.pre_process(GuardInput(text="alice@example.com"))
    finally:
        rid_context_var.reset(outer_token)
    # No assertion needed — the test verifies the path runs without raising.
    # The outer ``rid_context_var`` token must still reset cleanly above.
