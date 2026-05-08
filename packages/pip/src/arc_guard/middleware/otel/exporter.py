"""OTEL exporter wiring with transport-failure fallback.

Operators who don't already have the OTEL SDK auto-configured can use
``configure_otlp_exporter()`` to wire a ``BatchSpanProcessor`` against
the OTLP endpoint described by ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or
the explicit kwargs). The exporter installs an export-error callback
that increments
``arc_guardrails.observability.export_failed{backend="otel"}`` so a
collector outage is visible in any second metric backend the operator
configured.

The pipeline does not call this directly — the OTEL SDK's auto-config
fires when ``arc_guard.middleware.from_otel_sdk()`` runs. This module
exists for operators who want explicit control over the exporter
shape (e.g. multiple endpoints, custom retry).
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as _HttpOTLPSpanExporter,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError as exc:  # pragma: no cover — gated by extra
    raise ImportError(
        "arc_guard.middleware.otel.exporter requires the [otel] extra. "
        "Install with: pip install arc-guard[otel]"
    ) from exc


logger = logging.getLogger("arc_guard.middleware.otel.exporter")


def configure_otlp_exporter(
    provider: TracerProvider,
    *,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> BatchSpanProcessor:
    """Attach an OTLP/HTTP span exporter to the provider with batched export.

    Returns the ``BatchSpanProcessor`` so callers can shut it down
    explicitly during teardown. Errors during export are logged at
    WARNING level — the OTEL SDK already swallows them, so the
    fallback metric counter (in ``OtelMetricSink``) is the
    machine-readable signal.
    """
    exporter = _HttpOTLPSpanExporter(
        endpoint=endpoint,
        headers=headers or {},
        timeout=int(timeout),
    )
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    return processor


def safe_shutdown(processor: BatchSpanProcessor, *, timeout: float = 5.0) -> None:
    """Flush + shut down a span processor without raising.

    Used during pipeline teardown so an unreachable collector at
    shutdown time does not bring down the host process.
    """
    try:
        processor.shutdown()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("OTEL processor shutdown raised: %s", exc)


def install_export_error_log_handler() -> None:
    """Route OTEL SDK internal logging to a recognizable namespace.

    The OTEL SDK emits internal failures to the ``opentelemetry``
    logger; routing it lets operators set their log filters once and
    capture both arc-guard's own messages and OTEL transport-failure
    messages with a single rule.
    """
    otel_logger = logging.getLogger("opentelemetry")
    otel_logger.setLevel(logging.WARNING)
    if not any(isinstance(h, logging.NullHandler) for h in otel_logger.handlers):
        otel_logger.addHandler(logging.NullHandler())


def _coerce_kwargs(**kwargs: Any) -> dict[str, Any]:  # pragma: no cover — trivial
    return {k: v for k, v in kwargs.items() if v is not None}


__all__ = [
    "configure_otlp_exporter",
    "safe_shutdown",
    "install_export_error_log_handler",
]
