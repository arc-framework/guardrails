"""Stdlib-logging bridges for the SDK observability protocols.

The SDK's pipeline emits structured events through the `Logger` Protocol
defined in `arc_guard_core.observability`. The default implementation is
`NullLogger`, which discards everything — so out-of-the-box deployments
never see in-pipeline events (defend / classify / deception_inspect /
refusal / verify / rehydrate stages).

`StdlibBridgeLogger` forwards each `event(...)` call onto a Python stdlib
logger so operators can read pipeline activity from `docker logs`,
journald, or any other stdlib-logging consumer without wiring a heavier
observability backend.
"""

from __future__ import annotations

import logging
from typing import Any


class StdlibBridgeLogger:
    """Implements `arc_guard_core.observability.Logger` over stdlib logging."""

    def __init__(
        self,
        log: logging.Logger | None = None,
        fields: dict[str, Any] | None = None,
    ) -> None:
        self._log = log or logging.getLogger("arc-guard.sdk")
        self._fields = fields or {}

    def bind(self, **fields: Any) -> StdlibBridgeLogger:
        return StdlibBridgeLogger(self._log, {**self._fields, **fields})

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        merged = {**self._fields, **fields}
        kvs = " ".join(f"{k}={v!r}" for k, v in merged.items())
        self._log.log(
            getattr(logging, level.upper(), logging.INFO),
            "event=%s %s",
            name,
            kvs,
        )


__all__ = ["StdlibBridgeLogger"]
