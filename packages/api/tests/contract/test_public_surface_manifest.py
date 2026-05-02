"""Run the public-surface drift check against ``arc_guard_service``.

Wraps ``tools/check_public_surface.py`` so the per-package quality gate
runs the manifest-vs-runtime symmetric difference, the stability-band
consistency check, and the deprecation-shim check on every test run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOL_PATH = REPO_ROOT / "tools" / "check_public_surface.py"


@pytest.fixture(scope="module")
def check_module() -> object:
    spec = importlib.util.spec_from_file_location("_check_public_surface_api", TOOL_PATH)
    assert spec and spec.loader, f"could not load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_check_public_surface_api", module)
    spec.loader.exec_module(module)
    return module


def test_no_drift_for_arc_guard_service(check_module: object) -> None:
    errors = check_module.check_manifest()  # type: ignore[attr-defined]
    api_errors = [e for e in errors if "[arc_guard_service]" in e]
    assert api_errors == [], "\n".join(api_errors)


def test_full_check_passes(check_module: object) -> None:
    """All three packages combined: zero drift."""
    errors = check_module.check_manifest()  # type: ignore[attr-defined]
    assert errors == [], "\n".join(errors)
