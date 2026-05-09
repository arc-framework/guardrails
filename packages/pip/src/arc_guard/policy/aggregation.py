"""Aggregate-action selection driven by the run's risk band."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from arc_guard_core.policy import RiskBand
from arc_guard_core.types import PolicyDecision

from arc_guard.policy.conflict import _precedence_index

ActionLiteral = Literal["pass", "redact", "hash", "block", "tokenize"]


def aggregate_action_for_band(
    band: RiskBand, decisions: Sequence[PolicyDecision]
) -> ActionLiteral:
    """Choose the run-level aggregate action.

    - LOW / MEDIUM / HIGH → most restrictive non-block decision strategy.
      HIGH is a partial refusal: the action stays non-block and the
      refusal envelope carries the explanation; this preserves the
      caller's ability to render the sanitized text alongside a banner.
    - CRITICAL → ``"block"``.
    """
    if band == RiskBand.CRITICAL:
        return "block"
    if not decisions:
        return "pass"
    # Pick the most-restrictive non-block decision strategy.
    non_block = [d for d in decisions if d.strategy != "block"]
    pool = non_block or list(decisions)
    sorted_decisions = sorted(pool, key=lambda d: _precedence_index(d.strategy))
    chosen = sorted_decisions[0].strategy
    if band == RiskBand.HIGH and chosen == "block":
        # HIGH band must not surface as a hard block; fall back to redact
        # so the caller still gets sanitized text plus the refusal envelope.
        chosen = "redact"
    if chosen not in ("pass", "redact", "hash", "block", "tokenize"):
        chosen = "pass"
    return chosen  # type: ignore[return-value]


__all__ = ["aggregate_action_for_band"]
