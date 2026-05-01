from __future__ import annotations

from arc_guard_core.types import GuardResult


class NullReporter:
    """No-op reporter — discards all results. Useful in tests."""

    async def report(self, result: GuardResult) -> None:
        pass

    async def close(self) -> None:
        return None
