"""Service boots without network I/O.

Wraps ``socket.socket`` to count outbound connection attempts during
``create_app(...)``; asserts zero outbound network calls happen at boot.
Also asserts the boot completes well within the 2-second budget.
"""

from __future__ import annotations

import socket
import time

import pytest

from arc_guard_service.settings import ServiceSettings


def test_create_app_does_no_outbound_network_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_connect = socket.socket.connect
    outbound_attempts: list[object] = []

    def _wrapped_connect(self: socket.socket, address: object) -> None:  # type: ignore[type-arg]
        outbound_attempts.append(address)
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", _wrapped_connect)

    from arc_guard_service.transport.http import create_app

    start = time.perf_counter()
    app = create_app(ServiceSettings())
    elapsed = time.perf_counter() - start

    assert app is not None
    assert outbound_attempts == [], (
        f"create_app made outbound connections: {outbound_attempts}"
    )
    assert elapsed < 2.0, f"create_app boot took {elapsed:.2f}s, expected < 2.0s"


def test_run_guard_default_path_no_outbound_io(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    outbound_attempts: list[object] = []

    def _wrapped_connect(self: socket.socket, address: object) -> None:  # type: ignore[type-arg]
        outbound_attempts.append(address)
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", _wrapped_connect)

    from arc_guard_core.types import GuardInput

    from arc_guard_service import run_guard

    result = run_guard(GuardInput(text="hello"))
    assert result is not None
    assert outbound_attempts == [], (
        f"run_guard made outbound connections: {outbound_attempts}"
    )
