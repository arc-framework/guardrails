"""Exceptions raised inside ``pipeline.pre_process`` propagate unchanged.

The runner does not wrap pipeline exceptions: a ``JailbreakDetectorError``
raised inside the pipeline surfaces to the caller as the same type with
the same code, both from sync and from running-loop call sites.
"""

from __future__ import annotations

import pytest
from arc_guard_core.exceptions import JailbreakDetectorError
from arc_guard_core.types import GuardInput, GuardResult

from arc_guard_service import run_guard


class _RaisingPipeline:
    """Stub pipeline whose pre_process always raises."""

    async def pre_process(self, input: GuardInput) -> GuardResult:
        raise JailbreakDetectorError(
            "stub raise",
            code="jailbreak_detector.model_load_failed",
        )


def test_pipeline_exception_propagates_to_sync_caller() -> None:
    with pytest.raises(JailbreakDetectorError) as excinfo:
        run_guard(GuardInput(text="any"), pipeline=_RaisingPipeline())
    assert excinfo.value.code == "jailbreak_detector.model_load_failed"


@pytest.mark.asyncio
async def test_pipeline_exception_propagates_under_running_loop() -> None:
    with pytest.raises(JailbreakDetectorError) as excinfo:
        run_guard(GuardInput(text="any"), pipeline=_RaisingPipeline())
    assert excinfo.value.code == "jailbreak_detector.model_load_failed"
