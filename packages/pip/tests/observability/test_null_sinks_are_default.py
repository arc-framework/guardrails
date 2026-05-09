"""Null sinks are the default and produce no observable behavior.

When no observability hooks are configured, the pipeline must:
- import without warnings,
- produce a normal ``GuardResult`` for the input,
- not reach into globally-installed sinks for emissions.
"""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.pipeline import GuardPipeline


@pytest.mark.asyncio
async def test_default_pipeline_has_null_sinks_and_returns_normal_result() -> None:
    pipeline = GuardPipeline(inspectors=[])  # no tracer / logger / metric hooks

    result = await pipeline.pre_process(GuardInput(text="Hello, default."))

    assert result is not None
    # The default pipeline produces a pass-action result on benign input
    # because no findings fire and no policy ruleset is configured.
    assert result.action == "pass"
