"""T070 — simulating the removal release: shim raises ImportError after removed_in."""

from __future__ import annotations

import importlib
import sys
import warnings
from unittest.mock import patch

import pytest


def _reload_arc_guard() -> None:
    """Drop the cached arc_guard module so the next import re-runs the shim."""
    for name in list(sys.modules):
        if name == "arc_guard" or name.startswith("arc_guard._"):
            del sys.modules[name]


def test_post_removal_raises_import_error() -> None:
    """When CURRENT_VERSION >= entry.removed_in, the shim raises ImportError."""
    _reload_arc_guard()
    # Pretend we are in the removal release (0.3.0). After patching the
    # constant, importing any deprecated name must raise ImportError.
    legacy = importlib.import_module("arc_guard._legacy")
    with patch.object(legacy, "CURRENT_VERSION", "0.3.0"):
        import arc_guard

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(ImportError) as excinfo:
                _ = arc_guard.GuardResult  # type: ignore[attr-defined]

        msg = str(excinfo.value)
        assert "removed in arc-guard 0.3.0" in msg
        assert "arc_guard_core.types" in msg
        assert "GuardResult" in msg
        assert "002-rewrite-foundation" in msg or "migration" in msg.lower()

    # Cleanup so subsequent tests see the live (0.2.0) shim again.
    _reload_arc_guard()
