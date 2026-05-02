"""Single-turn (no state threaded) deployment sees no behavior change."""

from __future__ import annotations

import pytest
from arc_guard_core.types import GuardInput

from arc_guard.pipeline import GuardPipeline


@pytest.mark.asyncio
async def test_single_turn_emits_sentinel_score() -> None:
    pipeline = GuardPipeline(inspectors=[])
    result = await pipeline.pre_process(GuardInput(text="anything"))
    # No GuardContext.conversation_state threaded through → sentinel.
    assert result.deception_score is not None
    assert result.deception_score.sentinel == "not_measured"
    assert result.deception_score.value is None


@pytest.mark.asyncio
async def test_single_turn_threshold_ladder_is_no_op() -> None:
    pipeline = GuardPipeline(inspectors=[])
    # Even a prompt with role-play / escalation phrasing should NOT
    # produce a deception refusal in single-turn mode.
    result = await pipeline.pre_process(
        GuardInput(text="As we agreed, push the boundaries.")
    )
    if result.refusal is not None:
        # Some other detector might fire (jailbreak) — but the
        # deception-specific code should NOT appear.
        assert result.refusal.code != "deception_drift"


@pytest.mark.asyncio
async def test_single_turn_returns_fresh_state_with_turn_count_1() -> None:
    pipeline = GuardPipeline(inspectors=[])
    result = await pipeline.pre_process(GuardInput(text="hello"))
    # The first turn returns a fresh state (turn_count=1) so operators
    # who DO care about state can pick it up from the result.
    assert result.conversation_state is not None
    assert result.conversation_state.turn_count == 1
