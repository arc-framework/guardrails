from __future__ import annotations

from arc_guard.types import GuardResult


class NullReporter:
    """No-op reporter — discards all results. Useful in tests."""

    async def report(self, result: GuardResult) -> None:
        pass
