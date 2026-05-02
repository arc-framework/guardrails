"""arc_guard.middleware — pipeline middleware implementations.

The OTEL adapter lives at ``arc_guard.middleware.otel`` and is gated
by the ``arc-guard[otel]`` extra. The top-level ``from_otel_sdk()``
factory imports the OTEL adapter lazily so a bare
``import arc_guard.middleware`` succeeds whether or not the extra is
installed; the import-error message is friendly when the operator
calls the factory without the extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arc_guard.middleware.otel import OtelObservability  # noqa: F401


def from_otel_sdk(*, instrumentation_name: str = "arc-guardrails") -> Any:
    """Build OTEL-backed observability adapters from the SDK's
    auto-configured providers.

    Returns an ``OtelObservability`` bundle exposing ``.tracer``,
    ``.logger``, and ``.metric_sink`` attributes that satisfy the
    foundation's observability Protocols.

    Raises:
        ImportError: when ``arc-guard[otel]`` is not installed. The
            message tells the operator how to fix it.
    """
    try:
        from arc_guard.middleware.otel import OtelObservability
    except ImportError as exc:
        raise ImportError(
            "from_otel_sdk() requires the [otel] extra. "
            "Install with: pip install arc-guard[otel]"
        ) from exc
    return OtelObservability.from_otel_sdk(instrumentation_name=instrumentation_name)


__all__ = ["from_otel_sdk"]
