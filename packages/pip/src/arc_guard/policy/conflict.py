"""Strategy conflict resolution."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.policy import PolicyRule

# Highest-to-lowest restrictiveness. Resolution picks the most restrictive
# strategy when multiple rules match the same finding.
STRATEGY_PRECEDENCE: tuple[str, ...] = (
    "block",
    "redact",
    "tokenize",
    "hash",
    "warn",
    "pass",
)


def _precedence_index(strategy: str | None) -> int:
    """Return precedence index for a strategy name.

    Selector-based rules (``strategy is None``) have an unresolved strategy
    until routing time. We treat them as ``block``-precedence (most
    restrictive) so a selector rule wins against a permissive explicit
    strategy in a tie — the operator opted into framework-driven masking
    expecting a safe default.
    """
    if strategy is None:
        return STRATEGY_PRECEDENCE.index("block")
    try:
        return STRATEGY_PRECEDENCE.index(strategy)
    except ValueError:
        return len(STRATEGY_PRECEDENCE)


def resolve_conflict(
    candidate_rules: Sequence[PolicyRule],
) -> tuple[PolicyRule, tuple[PolicyRule, ...]]:
    """Pick the most-restrictive rule from candidates.

    Returns ``(winner, losers)`` so the router can record the resolution
    in the winning ``PolicyDecision.rationale``.
    """
    if not candidate_rules:
        raise ValueError("resolve_conflict: candidate_rules must be non-empty")
    sorted_rules = sorted(
        enumerate(candidate_rules),
        key=lambda pair: (_precedence_index(pair[1].strategy), pair[0]),
    )
    winner = sorted_rules[0][1]
    losers = tuple(rule for _, rule in sorted_rules[1:])
    return winner, losers


__all__ = ["STRATEGY_PRECEDENCE", "resolve_conflict"]
