"""Smoke test: the docs-link check fails when an internal link is broken.

Writes a temporary ``*.md`` under ``docs/`` with a deliberately broken
relative link, runs ``tools/check_docs_links.py`` programmatically, asserts
the check returns a non-zero exit and an error mentioning the broken target.
The temp file is removed in cleanup.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOL_PATH = REPO_ROOT / "tools" / "check_docs_links.py"


@pytest.fixture()
def link_check_module() -> object:
    spec = importlib.util.spec_from_file_location("_check_docs_links_smoke", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_docs_links_smoke"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("_check_docs_links_smoke", None)


def test_clean_repo_passes_link_check(link_check_module: object) -> None:
    errors = link_check_module.check_links()  # type: ignore[attr-defined]
    assert errors == [], "\n".join(errors)


def test_broken_link_triggers_drift_error(
    tmp_path_factory: pytest.TempPathFactory,
    link_check_module: object,
) -> None:
    bad = REPO_ROOT / "docs" / "_smoke_broken_link.md"
    bad.write_text("# smoke\n\nSee [missing](does-not-exist.md).\n", encoding="utf-8")
    try:
        errors = link_check_module.check_links()  # type: ignore[attr-defined]
        relevant = [e for e in errors if "_smoke_broken_link.md" in e]
        assert relevant, f"expected an error about the broken link; got: {errors}"
        assert any("does-not-exist" in e for e in relevant)
    finally:
        bad.unlink(missing_ok=True)
