"""PolicyRouter Protocol — routes findings to strategies."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.policy import PolicyRuleSet, RoutedOutcome
from arc_guard_core.types import GuardResult


@runtime_checkable
class PolicyRouter(Protocol):
    """Routes findings to strategies and aggregates the run-level outcome.

    Concurrency: sync. Implementations MUST be thread-safe — the pipeline
    may invoke from multiple coroutines / threads simultaneously.
    Thread-safety: thread-safe.

    Declared exceptions: ``PolicyRouterError`` (from the typed exception
    hierarchy). Internal failures MUST be caught and converted; the public
    API never propagates a raw ``PolicyRouterError``.

    Failure mode: closed. A router error produces a ``RefusalEnvelope``
    with a registered ``RefusalCode``. The pipeline never returns partial
    output on a routing error.
    """

    def route(
        self,
        result: GuardResult,
        ruleset: PolicyRuleSet,
    ) -> RoutedOutcome: ...
