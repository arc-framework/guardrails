from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from arc_guard_core.types import Finding, GuardResult, RiskLevel

import arc_guard.adapters.nats_reporter as mod
from arc_guard.adapters.nats_reporter import NatsReporter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(risk: RiskLevel = RiskLevel.MEDIUM) -> Finding:
    return Finding(
        entity_type="TEST_ENTITY",
        start=0,
        end=4,
        risk_level=risk,
        inspector="test",
    )


def _result(
    action: str = "pass",
    findings: tuple[Finding, ...] = (),
    phase: str = "pre_process",
    bypass_reason: Any = None,
) -> GuardResult:
    return GuardResult(
        text="some text",
        action=action,  # type: ignore[arg-type]
        findings=findings,
        phase=phase,  # type: ignore[arg-type]
        bypass_reason=bypass_reason,
    )


def _make_nc() -> AsyncMock:
    nc = AsyncMock()
    nc.publish = AsyncMock()
    return nc


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


class TestImportGuard:
    def test_raises_when_nats_unavailable(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", False):
            with pytest.raises(ImportError, match="arc-guard\\[nats\\]"):
                NatsReporter(_make_nc())

    def test_no_error_when_nats_available(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            reporter = NatsReporter(_make_nc())
        assert reporter is not None


# ---------------------------------------------------------------------------
# Constructor / defaults
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_default_subject(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc())
        assert r._subject == "arc.ai.guard.events"

    def test_custom_subject(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc(), subject="arc.reasoner.guard.rejected")
        assert r._subject == "arc.reasoner.guard.rejected"

    def test_explicit_queue_size(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc(), queue_size=42)
        assert r._queue.maxsize == 42

    def test_queue_size_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_REPORTER_QUEUE_SIZE", "250")
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc())
        assert r._queue.maxsize == 250

    def test_queue_size_default_1000(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GUARD_REPORTER_QUEUE_SIZE", raising=False)
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc())
        assert r._queue.maxsize == 1000


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------


class TestEventSchema:
    async def test_published_payload_schema(self) -> None:
        nc = _make_nc()
        with patch.object(mod, "_NATS_AVAILABLE", True):
            async with NatsReporter(nc, subject="arc.ai.guard.events", queue_size=10) as reporter:
                findings = (_finding(RiskLevel.HIGH), _finding(RiskLevel.MEDIUM))
                result = _result(action="redact", findings=findings, phase="pre_process")
                await reporter.report(result)
                # yield to drain loop
                await asyncio.sleep(0)

        # By the time __aexit__ returns, queue is drained
        nc.publish.assert_awaited_once()
        call_args = nc.publish.call_args
        subject_arg = call_args.args[0]
        payload_bytes = call_args.args[1]
        event = json.loads(payload_bytes.decode())

        assert subject_arg == "arc.ai.guard.events"
        assert event["schema_version"] == "1.0"
        assert event["phase"] == "pre_process"
        assert event["action"] == "redact"
        assert event["findings_count"] == 2
        assert event["max_risk"] == RiskLevel.HIGH.value
        assert event["bypass_reason"] is None
        assert event["subject"] == "arc.ai.guard.events"

    async def test_bypass_reason_included(self) -> None:
        nc = _make_nc()
        with patch.object(mod, "_NATS_AVAILABLE", True):
            async with NatsReporter(nc, queue_size=10) as reporter:
                result = _result(bypass_reason="disabled")
                await reporter.report(result)
                await asyncio.sleep(0)

        event = json.loads(nc.publish.call_args.args[1].decode())
        assert event["bypass_reason"] == "disabled"

    async def test_max_risk_none_when_no_findings(self) -> None:
        nc = _make_nc()
        with patch.object(mod, "_NATS_AVAILABLE", True):
            async with NatsReporter(nc, queue_size=10) as reporter:
                await reporter.report(_result())
                await asyncio.sleep(0)

        event = json.loads(nc.publish.call_args.args[1].decode())
        assert event["max_risk"] == RiskLevel.NONE.value
        assert event["findings_count"] == 0


# ---------------------------------------------------------------------------
# Drain loop / queue behaviour
# ---------------------------------------------------------------------------


class TestDrainLoop:
    async def test_drain_loop_started_lazily(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc(), queue_size=10)

        assert r._drain_started is False
        await r.report(_result())
        assert r._drain_started is True

    async def test_drain_loop_started_only_once(self) -> None:
        nc = _make_nc()
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(nc, queue_size=10)

        await r.report(_result())
        await r.report(_result())
        # Allow loop to drain
        await asyncio.sleep(0)
        assert r._drain_started is True
        assert nc.publish.await_count == 2

    async def test_publish_failure_does_not_crash_loop(self) -> None:
        nc = _make_nc()
        # First publish raises, second succeeds
        nc.publish.side_effect = [RuntimeError("nats down"), None]

        with patch.object(mod, "_NATS_AVAILABLE", True):
            async with NatsReporter(nc, queue_size=10) as reporter:
                await reporter.report(_result())
                await asyncio.sleep(0)
                await reporter.report(_result())
                await asyncio.sleep(0)

        assert nc.publish.await_count == 2

    async def test_report_never_raises(self) -> None:
        nc = _make_nc()
        nc.publish.side_effect = RuntimeError("catastrophic failure")
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(nc, queue_size=10)
        # Must not raise
        await r.report(_result())


# ---------------------------------------------------------------------------
# Queue-full / drop-oldest
# ---------------------------------------------------------------------------


class TestQueueFull:
    async def test_oldest_dropped_when_full(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        nc = _make_nc()
        # Pause publish so nothing drains
        publish_gate: asyncio.Event = asyncio.Event()

        async def _slow_publish(subject: str, payload: bytes) -> None:
            await publish_gate.wait()

        nc.publish.side_effect = _slow_publish

        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(nc, queue_size=2)

        # Fill queue without starting the drain (drain_started=False initially)
        # Put items directly to bypass the lazy-start
        r._queue.put_nowait(b"first")
        r._queue.put_nowait(b"second")
        # Queue is now full; report() should drop "first" and enqueue "third"
        with caplog.at_level(logging.WARNING, logger="arc_guard"):
            await r.report(_result(action="block"))

        assert "dropping oldest event" in caplog.text
        # Queue still has 2 items: "second" and the newly enqueued "block" payload
        assert r._queue.qsize() == 2
        items = []
        while not r._queue.empty():
            items.append(r._queue.get_nowait())
            r._queue.task_done()
        assert items[0] == b"second"
        event = json.loads(items[1].decode())
        assert event["action"] == "block"


# ---------------------------------------------------------------------------
# Async context manager
# ---------------------------------------------------------------------------


class TestAsyncContextManager:
    async def test_aenter_returns_self(self) -> None:
        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc(), queue_size=5)
        result = await r.__aenter__()
        assert result is r

    async def test_aexit_waits_for_queue_to_drain(self) -> None:
        nc = _make_nc()
        with patch.object(mod, "_NATS_AVAILABLE", True):
            async with NatsReporter(nc, queue_size=10) as reporter:
                await reporter.report(_result())
                await reporter.report(_result())
                await asyncio.sleep(0)

        # After __aexit__, all items published
        assert nc.publish.await_count == 2


# ---------------------------------------------------------------------------
# Reporter protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_satisfies_reporter_protocol(self) -> None:
        from arc_guard.protocols.reporter import Reporter

        with patch.object(mod, "_NATS_AVAILABLE", True):
            r = NatsReporter(_make_nc())
        assert isinstance(r, Reporter)
