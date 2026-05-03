"""Without the ``[fastapi]`` extra, the package still imports and run_guard works.

Simulates the extra being absent by patching ``sys.modules['fastapi']`` to
``None``; asserts ``import arc_guard_service`` succeeds, ``create_app(...)``
raises ``ImportError`` with the documented friendly message, and the
in-process ``run_guard`` path still produces a valid ``GuardResult``.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def test_create_app_without_fastapi_raises_friendly_importerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "fastapi", None)

    if "arc_guard_service.transport.http" in sys.modules:
        importlib.reload(sys.modules["arc_guard_service.transport.http"])

    from arc_guard_service.transport.http import create_app

    with pytest.raises(ImportError, match=r"\[fastapi\]"):
        create_app()


def test_run_guard_still_works_without_fastapi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from arc_guard_core.types import GuardInput

    from arc_guard_service import run_guard

    result = run_guard(GuardInput(text="hello"))
    assert result.action in {"pass", "block", "redact"}


def test_top_level_import_succeeds_without_fastapi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fastapi", None)

    if "arc_guard_service" in sys.modules:
        importlib.reload(sys.modules["arc_guard_service"])

    import arc_guard_service

    assert hasattr(arc_guard_service, "run_guard")
    assert hasattr(arc_guard_service, "ServiceSettings")
