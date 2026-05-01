"""arc_guard.middleware — pipeline middleware implementations.

Spec 002 trimmed the OTEL middleware out of this package. Spec 004 will
ship the OTEL implementation that wraps the ``arc_guard_core.observability``
hook surface (``Tracer``, ``Logger``, ``MetricSink``).

Spec 001 callers that imported ``OtelMiddleware`` from this package will
receive an ``ImportError`` directing them to wait for Spec 004 or to
provide their own middleware satisfying the ``Middleware`` Protocol.
"""

from __future__ import annotations

__all__: list[str] = []
