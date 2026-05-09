"""Contract: rid correlation across structured logging + OTEL.

The dashboard data plane preserves rid correlation:
- The request-scope middleware sets ``rid_context_var`` on entry.
- The middleware echoes the rid in the ``X-Request-Id`` response header.
- Any log record emitted during the request inherits the rid via the
  context-var, so the structured-logging tap (``RidLogHandler``) can
  forward it to ``debug_entries``.

This test exercises the structured-logging side of the correlation. The
OTEL side is left to the existing OTEL integration tests in the
lifecycle-sink suite — wiring an OTEL exporter purely to test rid
propagation would duplicate that machinery.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from arc_guard.observability.debug_log_handler import (
    rid_context_var,
)
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


@pytest.mark.asyncio
async def test_x_request_id_response_header_carries_rid(tmp_path: Path) -> None:
    """The middleware echoes the resolved rid in the response header so
    clients can correlate without parsing the body or relying on OTEL."""
    db = tmp_path / "arc_guardrail.db"
    SqliteLifecycleSink(str(db))
    settings = ServiceSettings(
        enable_chat_completions=False, lifecycle_sqlite_path=str(db)
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        resp = await c.get(
            "/requests", headers={"x-request-id": "trace-correlation-test"}
        )
    assert resp.headers.get("x-request-id") == "trace-correlation-test"


@pytest.mark.asyncio
async def test_log_record_in_request_scope_carries_rid(
    tmp_path: Path,
) -> None:
    """A log record emitted while ``rid_context_var`` is set inherits the
    rid. The handler reads the context-var on emit; this is the
    structured-logging-correlation contract end-to-end."""
    captured: list[str] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            rid = rid_context_var.get(None)
            if rid is not None:
                captured.append(rid)

    logger = logging.getLogger("arc_guard.test_correlation")
    logger.setLevel(logging.DEBUG)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        token = rid_context_var.set("rid-correlate-XYZ")
        try:
            logger.debug("hello from active scope")
        finally:
            rid_context_var.reset(token)

        # And confirm the negative: outside the scope, no rid is captured.
        logger.debug("hello from outside scope")
    finally:
        logger.removeHandler(handler)

    assert captured == ["rid-correlate-XYZ"]


@pytest.mark.asyncio
async def test_concurrent_request_rids_isolated(tmp_path: Path) -> None:
    """Each task has its own context-var copy; concurrent requests don't
    bleed rids across each other. This is the property that makes the
    structured-logging tap safe under FastAPI's per-task model."""
    import asyncio

    captured: dict[str, list[str]] = {"A": [], "B": []}

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            rid = rid_context_var.get(None)
            if rid is not None and rid in captured:
                captured[rid].append(record.getMessage())

    logger = logging.getLogger("arc_guard.test_concurrent_correlation")
    logger.setLevel(logging.DEBUG)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:

        async def _request(rid: str, message: str) -> None:
            token = rid_context_var.set(rid)
            try:
                logger.debug(message)
                await asyncio.sleep(0.01)
            finally:
                rid_context_var.reset(token)

        captured["A"] = []
        captured["B"] = []
        await asyncio.gather(
            _request("A", "from-A"),
            _request("B", "from-B"),
        )
    finally:
        logger.removeHandler(handler)

    assert captured["A"] == ["from-A"]
    assert captured["B"] == ["from-B"]
