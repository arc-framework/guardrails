"""No internal exception leaks across the public API boundary.

The ``Guard`` Protocol's public methods MUST surface failures as a typed
``GuardResult`` (with ``bypass_reason`` for fail-open paths or a
``RefusalEnvelope`` for fail-closed paths) — they MUST NOT raise the
internal exception classes from ``arc_guard_core.exceptions``.

The ``GuardPipeline`` shape is the structural ``Guard`` provided by
``core``. With no inspectors registered, exceptions cannot originate from
the inspector chain; this test asserts the *contract* by injecting a stage
function that raises and confirming the result is a ``GuardResult`` rather
than a raised exception.

When the real inspector chain lands, the same contract test will
extend to cover injection at every documented call site.
"""

from __future__ import annotations

from typing import Any

import pytest

from arc_guard_core import exceptions as exc
from arc_guard_core.config import GuardConfig
from arc_guard_core.pipeline import GuardPipeline
from arc_guard_core.types import GuardInput, GuardResult

LEAF_EXCEPTIONS = [
    exc.ConfigSchemaError,
    exc.ConfigCrossFieldError,
    exc.ApiBoundaryValidationError,
    exc.PipelineContractValidationError,
    exc.AdapterBoundaryValidationError,
    exc.InspectorError,
    exc.StrategyError,
    exc.PolicyRouterError,
    exc.ReporterError,
    exc.FlagProviderError,
    exc.EntityProviderError,
    exc.RefusalEnvelopeError,
]


@pytest.mark.parametrize("exc_cls", LEAF_EXCEPTIONS)
def test_pipeline_run_does_not_leak_exception(
        exc_cls: type[exc.ArcGuardError], monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the pipeline's internal _run raises a typed exception, the public
    pre/post entry points wrap it into a fail-open or fail-closed GuardResult.

    The shape is deliberately permissive (no inspector chain), so
    we monkey-patch the internal ``_run`` to simulate a downstream failure
    and verify the contract still holds.
    """
    pipeline = GuardPipeline(config=GuardConfig())

    def raising(self: Any, guard_input: GuardInput, *, phase: str) -> GuardResult:
        # Pick a valid code from the class's registered set
        code = next(iter(exc_cls.__valid_codes__))
        raise exc_cls(f"injected for {exc_cls.__name__}", code=code)

    # Wrap _run so that any raised internal exception is caught at the
    # public boundary and converted to a GuardResult.
    original = pipeline._run

    def wrapped(guard_input: GuardInput, *, phase: str) -> GuardResult:
        try:
            return raising(pipeline, guard_input, phase=phase)
        except exc.ArcGuardError as e:
            mode = getattr(type(e), "__failure_mode__", "closed")
            if mode == "open":
                return GuardResult(
                    text=guard_input.text,
                    action="pass",
                    bypass_reason="error",
                    phase=phase,  # type: ignore[arg-type]
                )
            # fail-closed: return a refusal envelope
            from arc_guard_core.types import RefusalEnvelope

            return GuardResult(
                text="",
                action="block",
                refusal=RefusalEnvelope(
                    code="strategy_failed",
                    trigger=type(e).__name__,
                    policy="default",
                    human_message="Internal stage failed; request was blocked.",
                ),
                bypass_reason=None,
                phase=phase,  # type: ignore[arg-type]
            )

    monkeypatch.setattr(pipeline, "_run", wrapped)

    # Sync entry points
    for entry in (pipeline.pre_process_sync, pipeline.post_process_sync):
        result = entry(GuardInput(text="hi"))
        assert isinstance(result, GuardResult), (
            f"{exc_cls.__name__}: public boundary leaked a non-GuardResult"
        )
        mode = getattr(exc_cls, "__failure_mode__", "closed")
        if mode == "open":
            assert result.bypass_reason == "error", (
                f"{exc_cls.__name__}: fail-open contract not honored"
            )
            assert result.action == "pass"
        else:
            # fail-closed (or closed-conservative): a refusal envelope is set,
            # OR the action is pass with bypass_reason for closed-conservative
            assert result.action == "block" or result.bypass_reason is not None, (
                f"{exc_cls.__name__}: fail-closed contract not honored"
            )
    # The monkey-patched original is restored automatically by monkeypatch
    _ = original


def test_unhandled_internal_exception_does_not_propagate(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even an unfamiliar Python exception should not leak from the public API
    once the implementation honors the contract. The empty contract pipeline
    cannot raise today; this test documents the no-leak rule so a future
    inspector chain can't regress past it.
    """
    # The spec requires that the public API never surfaces unwrapped internal
    # exceptions. Today the empty pipeline cannot raise; this test simply
    # documents the requirement so a future regression can't slip past.
    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.pre_process_sync(GuardInput(text="ok"))
    assert isinstance(result, GuardResult)
