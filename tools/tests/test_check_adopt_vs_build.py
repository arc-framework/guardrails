"""T075 — tests for tools/check_adopt_vs_build.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add tools/ to sys.path so the script is importable as a module.
TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_adopt_vs_build as cab  # noqa: E402


CORE_PYPROJECT_BASELINE = """
[project]
name = "arc-guard-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0"]
"""

CORE_PYPROJECT_WITH_NEW_DEP = """
[project]
name = "arc-guard-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0", "httpx>=0.25"]
"""


def test_no_new_deps_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    current = tmp_path / "pyproject.toml"
    current.write_text(CORE_PYPROJECT_BASELINE)

    def fake_baseline(rev: str) -> set[str]:
        return {"pydantic"}

    monkeypatch.setattr(cab, "_runtime_deps_at_revision", fake_baseline)
    rc = cab.main(["--current", str(current)])
    assert rc == 0


def test_new_dep_without_record_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    current = tmp_path / "pyproject.toml"
    current.write_text(CORE_PYPROJECT_WITH_NEW_DEP)

    monkeypatch.setattr(cab, "_runtime_deps_at_revision", lambda rev: {"pydantic"})
    monkeypatch.setattr(cab, "_libraries_md_mentions", lambda name: False)
    monkeypatch.setattr(cab, "_decisions_mention", lambda name: False)

    rc = cab.main(["--current", str(current)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "httpx" in out


def test_new_dep_with_libraries_md_entry_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "pyproject.toml"
    current.write_text(CORE_PYPROJECT_WITH_NEW_DEP)

    monkeypatch.setattr(cab, "_runtime_deps_at_revision", lambda rev: {"pydantic"})
    monkeypatch.setattr(cab, "_libraries_md_mentions", lambda name: name == "httpx")
    monkeypatch.setattr(cab, "_decisions_mention", lambda name: False)

    rc = cab.main(["--current", str(current)])
    assert rc == 0


def test_new_dep_with_referenced_adr_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "pyproject.toml"
    current.write_text(CORE_PYPROJECT_WITH_NEW_DEP)

    monkeypatch.setattr(cab, "_runtime_deps_at_revision", lambda rev: {"pydantic"})
    monkeypatch.setattr(cab, "_libraries_md_mentions", lambda name: False)
    monkeypatch.setattr(cab, "_decisions_mention", lambda name: name == "httpx")

    rc = cab.main(["--current", str(current)])
    assert rc == 0


def test_dev_only_change_does_not_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A change that only edits the dev group must not flag anything."""
    pyproject_with_only_dev_dep = """
[project]
name = "arc-guard-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0"]

[dependency-groups]
dev = ["pytest", "ruff", "mypy", "newdevtool"]
"""
    current = tmp_path / "pyproject.toml"
    current.write_text(pyproject_with_only_dev_dep)

    monkeypatch.setattr(cab, "_runtime_deps_at_revision", lambda rev: {"pydantic"})
    rc = cab.main(["--current", str(current)])
    assert rc == 0


def test_decisions_mention_matches_front_matter(tmp_path: Path) -> None:
    """The ADR-detection helper should pick up `dependency:` in YAML front matter."""
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    (decisions / "001-test.md").write_text(
        "---\n"
        "dependency: somedep\n"
        "status: adopted\n"
        "decided: 2026-05-01\n"
        "spec: 002-rewrite-foundation\n"
        "---\n"
        "\n"
        "Body of the ADR.\n"
    )

    import importlib

    import check_adopt_vs_build as cab2

    importlib.reload(cab2)
    cab2.DECISIONS_DIR = decisions  # redirect to tmp dir
    assert cab2._decisions_mention("somedep") is True
    assert cab2._decisions_mention("otherdep") is False
