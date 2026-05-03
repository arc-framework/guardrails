"""Smoke test: the surface-drift check fails when a new public name appears.

Patches ``arc_guard_service.__all__`` to add a bogus name, runs the
checker programmatically, and asserts a clear error pointing at the
missing manifest entry. Restores ``__all__`` afterwards so other tests
are unaffected.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOL_PATH = REPO_ROOT / "tools" / "check_public_surface.py"


@pytest.fixture()
def check_module() -> object:
    spec = importlib.util.spec_from_file_location("_check_public_surface_smoke", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_public_surface_smoke"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("_check_public_surface_smoke", None)


def test_extra_public_name_triggers_drift_error(
    check_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arc_guard_service

    original = list(arc_guard_service.__all__)
    monkeypatch.setattr(arc_guard_service, "BogusExtraSymbol", object(), raising=False)
    monkeypatch.setattr(arc_guard_service, "__all__", original + ["BogusExtraSymbol"])

    errors = check_module.check_manifest()  # type: ignore[attr-defined]
    relevant = [e for e in errors if "BogusExtraSymbol" in e]
    assert relevant, f"expected a drift error mentioning the bogus symbol; got: {errors}"
    assert any("not in manifest" in e for e in relevant)
