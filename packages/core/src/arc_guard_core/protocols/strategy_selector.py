"""StrategySelector protocol — picks a strategy name per detected entity.

Stateless. Returns the registered name of one of the strategies (`block`,
`hash`, `redact`, `tokenize`, `warn`); does not own the strategy
implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arc_guard_core.types import Finding, GuardResult


@runtime_checkable
class StrategySelector(Protocol):
    """Maps a detected entity + surrounding context to a registered strategy name.

    Concurrency: sync. Implementations MUST be functionally pure given the same
    ``(finding, guard_result)`` inputs. No side effects.

    Failure mode: closed. Exceptions raised by ``select()`` are caught at the
    pipeline boundary and converted to a closed-posture refusal envelope using
    ``RefusalCode.INTERNAL_PIPELINE_ERROR``. Implementations SHOULD prefer
    returning a documented safe default (e.g., ``"redact"``) over raising.

    Returning a strategy name not present in the strategy registry raises
    ``StrategyError`` at the pipeline boundary.
    """

    def select(
        self,
        finding: Finding,
        guard_result: GuardResult,
    ) -> str:
        """Return the registered name of the strategy to apply for ``finding``.

        Args:
            finding: The detected entity to mask.
            guard_result: The full pipeline-state-so-far, including all prior
                findings on the same input.

        Returns:
            A strategy name registered in the strategy registry.
        """
        ...


__all__ = ["StrategySelector"]
