"""The not_measured sentinel never triggers a fidelity-driven action."""

from __future__ import annotations

import pytest
from arc_guard_core.observability_config import (
    FidelityThresholds,
    ObservabilityConfig,
)
from arc_guard_core.types import GuardInput

from arc_guard.config_env import GuardConfig
from arc_guard.pipeline import GuardPipeline


@pytest.mark.asyncio
async def test_null_pair_with_aggressive_thresholds_takes_no_action() -> None:
    """Even with extremely tight thresholds, the null pair stays informational."""
    config = GuardConfig(
        observability=ObservabilityConfig(
            fidelity_thresholds=FidelityThresholds(
                warn=0.99, clarify=0.95, refuse=0.9,
            ),
        ),
    )
    pipeline = GuardPipeline(config=config, inspectors=[])

    for text in ("hello", "another input", "and a third"):
        result = await pipeline.pre_process(GuardInput(text=text))
        # Sentinel score never trips the ladder — action stays "pass".
        assert result.action == "pass"
        assert result.fidelity_warning is False
        assert result.clarification is None
        assert result.refusal is None
        # And the score itself is the documented sentinel.
        assert result.fidelity_score is not None
        assert result.fidelity_score.sentinel == "not_measured"
