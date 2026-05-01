"""T048 — aggregate_action_for_band tests (D3 + FR-011)."""

from __future__ import annotations

from arc_guard_core.policy import RiskBand
from arc_guard_core.types import PolicyDecision, RiskLevel

from arc_guard.policy.aggregation import aggregate_action_for_band


def _d(strategy: str) -> PolicyDecision:
    return PolicyDecision(
        finding_ids=(0,),
        strategy=strategy,
        severity=RiskLevel.LOW,
        rationale="t",
    )


def test_no_decisions_pass() -> None:
    assert aggregate_action_for_band(RiskBand.LOW, []) == "pass"


def test_critical_always_block() -> None:
    assert aggregate_action_for_band(RiskBand.CRITICAL, [_d("warn")]) == "block"
    assert aggregate_action_for_band(RiskBand.CRITICAL, []) == "block"


def test_low_picks_most_restrictive_non_block() -> None:
    decisions = [_d("warn"), _d("redact"), _d("hash")]
    # redact > hash > warn
    assert aggregate_action_for_band(RiskBand.LOW, decisions) == "redact"


def test_medium_picks_most_restrictive_non_block() -> None:
    decisions = [_d("hash"), _d("warn")]
    assert aggregate_action_for_band(RiskBand.MEDIUM, decisions) == "hash"


def test_high_never_block_per_d3() -> None:
    """D3 — HIGH band must never produce action='block'."""
    decisions = [_d("block"), _d("redact")]
    action = aggregate_action_for_band(RiskBand.HIGH, decisions)
    assert action != "block"


def test_high_only_block_decisions_falls_back_to_redact() -> None:
    """Edge case: every fired rule is `block` but band is HIGH — D3 forces non-block."""
    decisions = [_d("block")]
    assert aggregate_action_for_band(RiskBand.HIGH, decisions) == "redact"


def test_low_with_only_pass_decisions() -> None:
    decisions = [_d("pass")]
    assert aggregate_action_for_band(RiskBand.LOW, decisions) == "pass"
