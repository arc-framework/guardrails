"""arc_guard.policy — policy router, classifier, and conflict resolver.

The contract types live in ``arc_guard_core.policy``; this package provides
the runtime behavior.
"""

from __future__ import annotations

from arc_guard_core.exceptions import ConfigCrossFieldError
from arc_guard_core.policy import PolicyRuleSet


def validate_strategies_registered(ruleset: PolicyRuleSet) -> None:
    """Raise ConfigCrossFieldError if any rule references an unknown strategy.

    This is the runtime hook that ``GuardConfig.policy`` validation invokes
    when a pipeline is constructed.
    """
    from arc_guard.strategies.registry import is_registered

    for rule in ruleset.rules:
        if not is_registered(rule.strategy):
            raise ConfigCrossFieldError(
                f"PolicyRuleSet rule {rule.id!r} references unknown strategy {rule.strategy!r}",
                code="config.cross_field_violation",
                details={"rule_id": rule.id, "strategy": rule.strategy},
            )


__all__ = ["validate_strategies_registered"]
