"""``apply_deception_ladder`` is a no-op when score is the not_measured sentinel.

Belt-and-suspenders unit test for the sentinel-no-op guarantee at the
helper level. Integration coverage of the same property lives in
``test_single_turn_no_op.py``.
"""

from __future__ import annotations

from arc_guard_core.deception import NOT_MEASURED, DeceptionScore
from arc_guard_core.observability_config import DeceptionThresholds
from arc_guard_core.types import GuardResult

from arc_guard.deception.ladder import apply_deception_ladder


def test_sentinel_score_returns_unchanged_result() -> None:
    result = GuardResult(text="answer", action="pass")
    out = apply_deception_ladder(result, NOT_MEASURED, DeceptionThresholds())
    assert out.action == result.action
    assert out.clarification is None
    assert out.refusal is None


def test_sentinel_score_against_aggressive_thresholds_is_still_no_op() -> None:
    """Even with extreme thresholds, the sentinel never trips the ladder."""
    result = GuardResult(text="answer", action="pass")
    aggressive = DeceptionThresholds(refuse=0.4, clarify=0.2, warn=0.05)
    out = apply_deception_ladder(result, NOT_MEASURED, aggressive)
    assert out.action == result.action
    assert out.clarification is None
    assert out.refusal is None


def test_explicit_not_measured_constructor_round_trip() -> None:
    """``DeceptionScore.not_measured()`` equals the module-level NOT_MEASURED."""
    explicit = DeceptionScore.not_measured()
    assert explicit == NOT_MEASURED

    result = GuardResult(text="x", action="pass")
    out = apply_deception_ladder(result, explicit, DeceptionThresholds())
    assert out.action == "pass"
    assert out.clarification is None
    assert out.refusal is None
