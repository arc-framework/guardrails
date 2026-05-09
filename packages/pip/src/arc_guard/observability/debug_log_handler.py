"""Structured-logging tap that captures stdlib log records carrying an active
``rid`` context-var and forwards them to ``DebugEntryWriter``.

Mechanism:

- ``rid_context_var`` is a ``contextvars.ContextVar[str | None]`` set by the
  api request-scope middleware on entry and reset on exit.
- ``RidLogHandler`` is a ``logging.Handler`` registered once on the root
  logger at app boot. On each ``LogRecord`` it reads the active value;
  records with ``rid is None`` are skipped (server-boot logs, retention
  task logs, etc.).
- Records with an active rid are forwarded to ``DebugEntryWriter.write()``
  which non-blockingly persists them to the ``debug_entries`` table.

The handler does not inspect or rewrite the log format — operators retain
full control over log formatting via their existing handlers.
"""

from __future__ import annotations

import contextvars
import logging
from datetime import UTC, datetime
from typing import Any

from arc_guard.observability.debug_entry_writer import DebugEntryWriter

# The single context-var the api request-scope middleware sets per request.
# Module-level so the handler and the middleware can both reference it.
rid_context_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "arc_guard_rid", default=None
)


_STDLIB_LOGRECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "asctime",
        "message",
    }
)


def _safe_metadata(record: logging.LogRecord) -> dict[str, Any]:
    """Extract the non-stdlib fields from ``record.__dict__`` and return
    only JSON-safe values (str, int, float, bool, None, list, dict). Other
    values are repr()'d to keep the writer from crashing on unserializable
    objects."""
    extras: dict[str, Any] = {}
    for k, v in record.__dict__.items():
        if k in _STDLIB_LOGRECORD_KEYS or k.startswith("_"):
            continue
        if isinstance(v, (str, int, float, bool, type(None))):
            extras[k] = v
        elif isinstance(v, (list, tuple)):
            extras[k] = [
                x if isinstance(x, (str, int, float, bool, type(None))) else repr(x)
                for x in v
            ]
        elif isinstance(v, dict):
            extras[k] = {
                str(kk): (
                    vv
                    if isinstance(vv, (str, int, float, bool, type(None)))
                    else repr(vv)
                )
                for kk, vv in v.items()
            }
        else:
            extras[k] = repr(v)
    return extras


class RidLogHandler(logging.Handler):
    """Log handler that writes records tagged with an active rid into
    ``debug_entries``. Records without an active rid are skipped silently."""

    def __init__(
        self,
        writer: DebugEntryWriter,
        *,
        level: int = logging.DEBUG,
    ) -> None:
        super().__init__(level=level)
        self._writer = writer
        # The handler must not call back into the logging system for its own
        # errors — that would recurse. The stdlib base class handles this
        # correctly via Handler.handleError; we override to silently swallow
        # the error rather than print to stderr.

    def emit(self, record: logging.LogRecord) -> None:
        rid = rid_context_var.get(None)
        if rid is None:
            return
        try:
            ts = datetime.fromtimestamp(record.created, tz=UTC)
            metadata = _safe_metadata(record)
            # write() is async; schedule on the running loop. If no loop is
            # running (logging from outside async context), drop silently —
            # the only expected callers are FastAPI handlers which always
            # run inside a loop.
            try:
                import asyncio

                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            asyncio.ensure_future(
                self._writer.write(
                    rid=rid,
                    ts=ts,
                    channel=record.name,
                    severity=record.levelname,
                    message=record.getMessage(),
                    metadata=metadata,
                ),
                loop=loop,
            )
        except Exception:  # noqa: BLE001 — log handler must not raise
            self.handleError(record)


__all__ = ["RidLogHandler", "rid_context_var"]
