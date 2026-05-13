"""arc_guard.policy — policy router, classifier, and conflict resolver.

The contract types live in ``arc_guard_core.policy``; this package provides
the runtime behavior.
"""

from __future__ import annotations

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.policy import PolicyRuleSet


def validate_strategies_registered(ruleset: PolicyRuleSet) -> None:
    """Raise ConfigCrossFieldError if any rule references an unknown strategy
    or unknown selector.

    For rules using ``strategy``, the strategy name must resolve in the
    strategy registry. For rules using ``selector``, the selector name must
    resolve in the selector registry. ``PolicyRule``'s mutex validator
    guarantees exactly one of the two is set.
    """
    from arc_guard.selectors.registry import is_registered as selector_is_registered
    from arc_guard.strategies.registry import is_registered as strategy_is_registered

    for rule in ruleset.rules:
        if rule.strategy is not None:
            if not strategy_is_registered(rule.strategy):
                raise ConfigCrossFieldError(
                    f"PolicyRuleSet rule {rule.id!r} references unknown strategy {rule.strategy!r}",
                    code="config.cross_field_violation",
                    details={"rule_id": rule.id, "strategy": rule.strategy},
                )
        else:
            assert rule.selector is not None  # mutex validator guarantees this
            if not selector_is_registered(rule.selector):
                raise ConfigCrossFieldError(
                    f"PolicyRuleSet rule {rule.id!r} references unknown selector {rule.selector!r}",
                    code="config.cross_field_violation",
                    details={"rule_id": rule.id, "selector": rule.selector},
                )


__all__ = ["validate_strategies_registered"]
