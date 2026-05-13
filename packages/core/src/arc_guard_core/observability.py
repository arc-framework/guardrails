"""Observability hook surface for arc-guard-core.

Three Protocol interfaces — ``Tracer``, ``Logger``, ``MetricSink`` — plus
null-object implementations that can be used as defaults. A future
observability implementation will substitute concrete OTEL-backed
implementations from ``arc_guard.middleware`` without re-shaping these
contracts.

Stability: ``@experimental`` until that implementation lands.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tracer(Protocol):
    """Trace span emitter.

    Concurrency: must be safe to call from multiple threads / coroutines.
    Failure mode: implementations must not raise back into the pipeline; log
    and swallow on internal errors.
    """

    def start_span(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Any]: ...


@runtime_checkable
class Logger(Protocol):
    """Structured event logger.

    Concurrency: thread-safe.
    Failure mode: implementations must not raise.
    """

    def bind(self, **fields: Any) -> Logger: ...

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None: ...


@runtime_checkable
class MetricSink(Protocol):
    """Counter / histogram emitter.

    Concurrency: thread-safe.
    Failure mode: implementations must not raise.
    """

    def counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Null implementations — default when no concrete backend is supplied.
# ---------------------------------------------------------------------------


class NullTracer:
    def start_span(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Any]:
        return nullcontext()


class NullLogger:
    def bind(self, **fields: Any) -> NullLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        return None


class NullMetricSink:
    def counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        return None

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        return None


__all__ = [
    "Tracer",
    "Logger",
    "MetricSink",
    "NullTracer",
    "NullLogger",
    "NullMetricSink",
]
