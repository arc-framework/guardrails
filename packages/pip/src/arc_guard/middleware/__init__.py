"""arc_guard.middleware — pipeline middleware implementations.

The OTEL middleware was trimmed out of this package. A future
observability implementation will wrap the ``arc_guard_core.observability``
hook surface (``Tracer``, ``Logger``, ``MetricSink``).

Historical callers that imported ``OtelMiddleware`` from this package
receive an ``ImportError``; they should either wait for the
observability implementation or supply their own ``Middleware``.
"""

from __future__ import annotations

__all__: list[str] = []
