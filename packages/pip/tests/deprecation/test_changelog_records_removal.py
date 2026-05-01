"""Every active deprecation entry has a corresponding CHANGELOG line."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_guard._legacy import LEGACY_SYMBOLS

CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.university"


def test_changelog_exists() -> None:
    assert CHANGELOG.is_file(), f"missing {CHANGELOG}"


@pytest.fixture(scope="module")
def changelog_text() -> str:
    return CHANGELOG.read_text()


def test_changelog_records_deprecation_section(changelog_text: str) -> None:
    assert "Deprecated" in changelog_text or "deprecated" in changelog_text.lower(), (
        "CHANGELOG.university must include a Deprecated section while shims are live"
    )


def test_changelog_mentions_removal_release(changelog_text: str) -> None:
    # Every legacy entry's removed_in version must appear in the changelog at
    # least once (typically in the deprecation section's "removed in vX.Y.Z"
    # phrasing). The audit guarantees the changelog and the
    # deprecation table cannot drift out of sync.
    versions = {entry.removed_in for entry in LEGACY_SYMBOLS.values()}
    for version in versions:
        assert version in changelog_text, (
            f"CHANGELOG.university must reference removal version {version} (US4 acceptance scenario 3)"
        )
