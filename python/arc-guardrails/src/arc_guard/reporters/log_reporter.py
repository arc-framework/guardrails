from __future__ import annotations

import logging

from arc_guard.types import GuardResult

logger = logging.getLogger("arc_guard")


class LogReporter:
    """Logs a warning for each non-clean GuardResult."""

    async def report(self, result: GuardResult) -> None:
        """Emit a warning log when *result* contains findings."""
        if not result.is_clean:
            logger.warning(
                "arc_guard: action=%s findings=%d max_risk=%s bypass_reason=%s",
                result.action,
                len(result.findings),
                result.max_risk.name,
                result.bypass_reason,
            )
