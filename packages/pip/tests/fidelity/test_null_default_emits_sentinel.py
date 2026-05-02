"""With no encoder/scorer overrides, every run gets the not_measured sentinel."""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.pipeline import GuardPipeline


@pytest.mark.asyncio
async def test_null_defaults_attach_not_measured_sentinel() -> None:
    pipeline = GuardPipeline(inspectors=[])
    inputs = [f"input {i}" for i in range(10)]
    for text in inputs:
        result = await pipeline.pre_process(GuardInput(text=text))
        assert result.fidelity_score is not None
        assert result.fidelity_score.sentinel == "not_measured"
        assert result.fidelity_score.value is None


@pytest.mark.asyncio
async def test_null_defaults_do_not_set_fidelity_warning() -> None:
    pipeline = GuardPipeline(inspectors=[])
    result = await pipeline.pre_process(GuardInput(text="anything"))
    assert result.fidelity_warning is False
