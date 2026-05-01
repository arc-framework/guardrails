from __future__ import annotations

import logging
from typing import Any

from arc_guard_core.types import GuardResult

logger = logging.getLogger("arc_guard")

try:
    import httpx as _httpx_mod  # type: ignore[import-not-found]

    _HTTPX_AVAILABLE = True
except ImportError:
    _httpx_mod = None  # noqa: F841
    _HTTPX_AVAILABLE = False


def _result_to_dict(result: GuardResult) -> dict[str, Any]:
    findings = [
        {
            "entity_type": f.entity_type,
            "start": f.start,
            "end": f.end,
            "risk_level": f.risk_level.value,
            "inspector": f.inspector,
            "score": f.score,
            "metadata": f.metadata,
        }
        for f in result.findings
    ]
    return {
        "text": result.text,
        "action": result.action,
        "findings": findings,
        "bypass_reason": result.bypass_reason,
        "phase": result.phase,
    }


class WebhookReporter:
    """POSTs GuardResult as JSON to a configured URL.

    Requires the ``httpx`` package (install ``arc-guard[webhook]``).
    """

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        if not _HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for WebhookReporter. "
                "Install it with: pip install arc-guard[webhook]"
            )
        self._url = url
        self._timeout = timeout

    async def report(self, result: GuardResult) -> None:
        """POST *result* to the configured webhook URL; never raises."""
        try:
            async with _httpx_mod.AsyncClient(timeout=self._timeout) as client:
                await client.post(self._url, json=_result_to_dict(result))
        except Exception as exc:
            logger.warning("arc_guard: WebhookReporter failed to deliver: %s", exc)

    async def close(self) -> None:
        return None
