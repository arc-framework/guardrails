"""Run the supported public-surface check against ``arc_guard_core``.

Wraps ``tools/check_public_surface.py`` so the per-package quality gate
verifies the documented supported imports still resolve, stable kinds still
match, and deprecation shims remain wired.
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
    spec = importlib.util.spec_from_file_location("_check_public_surface", TOOL_PATH)
    assert spec and spec.loader, f"could not load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_check_public_surface", module)
    spec.loader.exec_module(module)
    return module


def test_no_drift_for_arc_guard_core(check_module: object) -> None:
    errors = check_module.check_manifest()  # type: ignore[attr-defined]
    core_errors = [e for e in errors if "[arc_guard_core]" in e]
    assert core_errors == [], "\n".join(core_errors)
