"""OtelMiddleware — emits OTEL metrics and spans around pipeline calls.

WARNING: ``OtelMiddleware`` instances are stateful per pipeline call (they store
``_start_time`` and ``_span_ctx`` between ``before()`` and ``after()``).  Do NOT
share a single ``OtelMiddleware`` instance across concurrent pipeline calls.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from arc_guard.types import GuardInput, GuardResult

logger = logging.getLogger("arc_guard")

try:
    from opentelemetry import metrics, trace  # type: ignore[import-not-found]

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


class OtelMiddleware:
    """Middleware that emits OTEL metrics and spans around pipeline calls.

    Emits five metrics:

    * ``arc_guard.pipeline.duration_ms`` — full pipeline call duration (histogram)
    * ``arc_guard.inspector.duration_ms`` — per-inspector duration (histogram)
    * ``arc_guard.findings.count`` — number of findings produced (counter)
    * ``arc_guard.pipeline.errors`` — inspector exceptions caught by pipeline (counter)
    * ``arc_guard.reporter.dropped`` — events dropped from reporter queue (counter)

    And wraps each pipeline call in a span named ``arc_guard.pre_process``.

    If the OTEL SDK has no exporter configured, all metrics and spans are no-ops
    — this is standard OTEL behaviour and requires no special handling.

    Args:
        meter_name: The OTEL meter/tracer name. Defaults to ``"arc_guard"``.

    Raises:
        ImportError: If ``opentelemetry-api`` is not installed
            (hint: ``pip install arc-guard[otel]``).

    Note:
        Instances are stateful per pipeline call (``_start_time``, ``_span_ctx``).
        Do NOT share one instance across concurrent pipeline calls.
    """

    def __init__(self, meter_name: str = "arc_guard") -> None:
        if not _OTEL_AVAILABLE:
            raise ImportError(
                "opentelemetry-api is required for OtelMiddleware. "
                "Install it with: pip install arc-guard[otel]"
            )

        meter = metrics.get_meter(meter_name)
        self._tracer: Any = trace.get_tracer(meter_name)

        self._pipeline_duration: Any = meter.create_histogram(
            "arc_guard.pipeline.duration_ms",
            description="Full pipeline call duration in milliseconds",
            unit="ms",
        )
        self._inspector_duration: Any = meter.create_histogram(
            "arc_guard.inspector.duration_ms",
            description="Per-inspector duration in milliseconds",
            unit="ms",
        )
        self._findings_count: Any = meter.create_counter(
            "arc_guard.findings.count",
            description="Number of findings produced",
        )
        self._pipeline_errors: Any = meter.create_counter(
            "arc_guard.pipeline.errors",
            description="Inspector exceptions caught by pipeline",
        )
        self._reporter_dropped: Any = meter.create_counter(
            "arc_guard.reporter.dropped",
            description="Events dropped from reporter queue",
        )

        # Per-call state; only valid between before() and after().
        self._start_time: float = 0.0
        self._span_ctx: Any = None
        self._span: Any = None

    async def before(self, guard_input: GuardInput) -> GuardInput:
        """Record the pipeline start time and open a tracing span.

        Fail-open: if any OTEL call raises, a warning is logged and the original
        *guard_input* is returned unchanged.
        """
        try:
            self._start_time = time.monotonic()
            self._span_ctx = self._tracer.start_as_current_span("arc_guard.pre_process")
            self._span = self._span_ctx.__enter__()
        except Exception as exc:
            logger.warning("OtelMiddleware.before() raised: %s — continuing without tracing", exc)
        return guard_input

    async def after(self, result: GuardResult) -> GuardResult:
        """Record pipeline duration, findings count, and close the tracing span.

        Fail-open: if any OTEL call raises, a warning is logged and *result* is
        returned unchanged.
        """
        try:
            duration_ms = (time.monotonic() - self._start_time) * 1000
            self._pipeline_duration.record(duration_ms)
            self._findings_count.add(
                len(result.findings),
                {"action": result.action},
            )
            if self._span_ctx is not None:
                try:
                    if self._span is not None:
                        self._span.set_attribute("guard.action", result.action)
                        self._span.set_attribute("guard.findings_count", len(result.findings))
                finally:
                    self._span_ctx.__exit__(None, None, None)
                    self._span_ctx = None
                    self._span = None
        except Exception as exc:
            logger.warning("OtelMiddleware.after() raised: %s — returning result unchanged", exc)
        return result
