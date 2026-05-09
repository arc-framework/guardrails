"""``arc_guard.middleware`` imports cleanly without the [otel] extra.

The lazy-import factory must:

- let ``import arc_guard.middleware`` succeed regardless of whether
  ``opentelemetry`` is installed (the bare import path),
- expose ``from_otel_sdk`` as a callable on the module surface,
- raise a friendly ``ImportError`` (with install hint) when the
  factory is called and the extra is missing.

The "extra missing" path is simulated by patching ``sys.modules`` so
``opentelemetry`` looks unimportable to the lazy import — this avoids
needing a separate venv to test the unhappy path.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import pytest


def test_bare_middleware_import_does_not_pull_opentelemetry() -> None:
    """Importing ``arc_guard.middleware`` must not eagerly import OTEL."""
    # Snapshot the loaded modules before the bare import.
    before = set(sys.modules)
    importlib.import_module("arc_guard.middleware")
    after = set(sys.modules)

    pulled = {m for m in (after - before) if m.startswith("opentelemetry")}
    # If opentelemetry was already loaded by an earlier test in the
    # same session, this assertion can't prove the bare import is
    # lazy. The "extra missing" simulation below covers that case.
    assert not pulled or any("opentelemetry" in mod for mod in before), (
        f"bare arc_guard.middleware import pulled OTEL: {pulled}"
    )


def test_from_otel_sdk_is_present_on_module_surface() -> None:
    """The factory must be reachable via direct import.

    Use ``importlib.import_module`` rather than attribute access on
    ``arc_guard`` because earlier tests in the same session may have
    cleared ``arc_guard`` from ``sys.modules`` (the deprecation
    post-removal test does this), leaving the parent attribute
    unset even though the submodule is still cached.
    """
    middleware_module = importlib.import_module("arc_guard.middleware")
    assert callable(middleware_module.from_otel_sdk)


def test_from_otel_sdk_raises_friendly_import_error_when_extra_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate the [otel] extra being absent and assert the factory
    raises with an actionable install hint.
    """
    middleware_module = importlib.import_module("arc_guard.middleware")

    # Drop the otel sub-module + opentelemetry from sys.modules so the
    # next import attempt fails. Cache the originals so we can restore
    # them after the test (pytest's monkeypatch.delitem does not
    # auto-restore — only setattr does).
    blocked = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name == "arc_guard.middleware.otel"
        or name.startswith("arc_guard.middleware.otel.")
        or name.startswith("opentelemetry")
    }
    for name in blocked:
        del sys.modules[name]

    class _BlockOpenTelemetry:
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
            if fullname.startswith("opentelemetry"):
                raise ImportError(f"simulated absence of {fullname!r}")
            return None

    finder = _BlockOpenTelemetry()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    try:
        with pytest.raises(ImportError, match=r"\[otel\] extra"):
            middleware_module.from_otel_sdk()
    finally:
        # Restore the previously-loaded modules so subsequent tests in
        # the same session see the real OTEL import path.
        for name, module in blocked.items():
            sys.modules[name] = module
