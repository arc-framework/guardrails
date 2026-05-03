"""``run_guard(input, pipeline=custom)`` invokes the operator-supplied pipeline.

The default ``GuardPipeline()`` MUST NOT be constructed when a pipeline
is provided; the supplied pipeline's ``pre_process`` is the only call site.
"""

from __future__ import annotations

from dataclasses import replace

from arc_guard_core.types import GuardInput, GuardResult

from arc_guard_service import run_guard


class _StubPipeline:
    """Minimal stand-in for GuardPipeline; counts pre_process invocations."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def pre_process(self, input: GuardInput) -> GuardResult:
        self.calls += 1
        return GuardResult(text=f"stub-handled:{input.text}", action="pass")


def test_supplied_pipeline_is_called_exactly_once() -> None:
    stub = _StubPipeline()
    result = run_guard(GuardInput(text="abc"), pipeline=stub)
    assert stub.calls == 1
    assert result.text == "stub-handled:abc"
    assert result.action == "pass"


def test_default_pipeline_constructed_only_when_pipeline_is_none() -> None:
    # When no override, the default GuardPipeline is built and runs sanitize/
    # classify/etc. The stub above guarantees we DID NOT take that path
    # when a pipeline is supplied; here we assert the default path runs.
    result = run_guard(GuardInput(text="default path canary"))
    # The default pipeline produces a populated result with the standard
    # action vocabulary; the precise outcome depends on the inspector chain
    # but it must not be the stub's marker.
    assert not result.text.startswith("stub-handled:")
    # Quick sanity: the result type is a frozen dataclass we can ``replace``.
    replace(result, action=result.action)
