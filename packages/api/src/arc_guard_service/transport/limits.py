"""Request-size and request-timeout middlewares.

Both run as ASGI/Starlette middlewares; both produce a structured
``RefusalEnvelope`` response on violation, never a raw exception trace.

- ``RequestSizeLimitMiddleware`` rejects bodies larger than the configured
  byte limit with HTTP 413 + ``RefusalCode.API_INVALID_REQUEST``.
- ``RequestTimeoutMiddleware`` aborts handler execution that exceeds the
  configured deadline with HTTP 504 + ``RefusalCode.API_TRANSPORT_TIMEOUT``,
  and increments the ``arc_guardrails.api.timeout`` counter.

Co-located in one module because both share the "transport-level rejection
that produces a structured refusal envelope" concern; splitting them across
two files would force readers to context-switch when reasoning about the
boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from arc_guard_service.transport.errors import (
    envelope_for_invalid_request,
    envelope_for_transport_timeout,
)

Message: TypeAlias = dict[str, Any]
Scope: TypeAlias = dict[str, Any]
Receive: TypeAlias = Callable[[], Awaitable[Message]]
Send: TypeAlias = Callable[[Message], Awaitable[None]]
ASGIApp: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[None]]


_FASTAPI_INSTALL_HINT = (
    "arc-guard-service[fastapi] is not installed. "
    "Install it with: pip install arc-guard-service[fastapi]"
)


def _json_response(*, status_code: int, content: dict[str, Any]) -> Any:
    try:
        responses_module = importlib.import_module("starlette.responses")
    except ImportError as exc:
        raise ImportError(_FASTAPI_INSTALL_HINT) from exc
    response_cls = responses_module.JSONResponse
    return response_cls(status_code=status_code, content=content)


class RequestSizeLimitMiddleware:
    """Reject requests whose body exceeds ``max_bytes``.

    Inspects the ``content-length`` header when present. When absent
    (chunked transfer), wraps the receive callable so each chunk is
    counted; the first chunk that pushes the running total past
    ``max_bytes`` triggers rejection.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        content_length_raw = headers.get("content-length")
        if content_length_raw is not None:
            try:
                content_length = int(content_length_raw)
            except ValueError:
                content_length = None
            if content_length is not None and content_length > self.max_bytes:
                await self._reject(send)
                return

        bytes_seen = 0
        max_bytes = self.max_bytes
        body_overflow = False

        async def _wrapped_receive() -> Message:
            nonlocal bytes_seen, body_overflow
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"") or b""
                bytes_seen += len(body)
                if bytes_seen > max_bytes:
                    body_overflow = True
            return message

        if body_overflow:
            await self._reject(send)
            return

        async def _send_intercept(message: Message) -> None:
            nonlocal body_overflow
            if body_overflow:
                return
            await send(message)

        try:
            await self.app(scope, _wrapped_receive, _send_intercept)
        finally:
            if body_overflow:
                await self._reject(send)

    async def _reject(self, send: Send) -> None:
        envelope = envelope_for_invalid_request(trigger="transport.payload_too_large")
        response = _json_response(
            status_code=413,
            content=_envelope_to_dict(envelope),
        )
        await response(
            {"type": "http"},
            self._noop_receive,
            send,
        )

    @staticmethod
    async def _noop_receive() -> Message:
        return {"type": "http.disconnect"}


class RequestTimeoutMiddleware:
    """Abort request handling that exceeds ``timeout_seconds``.

    Wraps the downstream call in ``asyncio.wait_for``; on timeout, returns
    HTTP 504 with a structured refusal envelope. Calls the supplied
    ``on_timeout`` callable (used to increment the timeout counter).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        timeout_seconds: float,
        on_timeout: Callable[[], None] | None = None,
        skip_paths: tuple[str, ...] = ("/events",),
    ) -> None:
        self.app = app
        self.timeout_seconds = timeout_seconds
        self.on_timeout = on_timeout
        # Long-poll / Server-Sent-Event endpoints are infinite by design;
        # applying a per-request timeout would terminate them after the
        # window. Such paths bypass the timeout entirely.
        self.skip_paths = skip_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("path") in self.skip_paths:
            await self.app(scope, receive, send)
            return

        completed = asyncio.Event()
        timed_out = False
        send_lock = asyncio.Lock()

        async def _send_guarded(message: Message) -> None:
            async with send_lock:
                if not timed_out:
                    await send(message)

        async def _run() -> None:
            try:
                await self.app(scope, receive, _send_guarded)
            finally:
                completed.set()

        try:
            await asyncio.wait_for(_run(), timeout=self.timeout_seconds)
        except TimeoutError:
            timed_out = True
            if self.on_timeout is not None:
                with contextlib.suppress(Exception):
                    self.on_timeout()
            envelope = envelope_for_transport_timeout()
            response = _json_response(
                status_code=504,
                content=_envelope_to_dict(envelope),
            )
            async with send_lock:
                await response(
                    scope,
                    receive,
                    send,
                )


def _envelope_to_dict(envelope: Any) -> dict[str, Any]:
    """Serialize a ``RefusalEnvelope`` (frozen dataclass) to a JSON-friendly dict."""
    return {
        "code": envelope.code,
        "trigger": envelope.trigger,
        "policy": envelope.policy,
        "human_message": envelope.human_message,
        "next_steps": list(envelope.next_steps),
        "metadata": dict(envelope.metadata),
    }


__all__ = [
    "RequestSizeLimitMiddleware",
    "RequestTimeoutMiddleware",
]
