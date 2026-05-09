"""Smoke test: custom extensions stay compact.

Custom Protocol-based extensions (StrategySelector, ContentPolicy)
should fit comfortably under 50 lines of code each. This test guards
against accidental complexity creep in the public extension surface.
"""

from __future__ import annotations

import inspect


def _count_meaningful_lines(source: str) -> int:
    """Lines that contain code (excluding blank lines and comment-only lines)."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def test_entitlements_selector_under_50_loc() -> None:
    from tests.integration.test_custom_selector_only_core_imports import (
        EntitlementsBasedSelector,
    )

    src = inspect.getsource(EntitlementsBasedSelector)
    loc = _count_meaningful_lines(src)
    assert loc < 50, (
        f"EntitlementsBasedSelector is {loc} meaningful LOC; the custom "
        "selector example should stay under 50."
    )


def test_regex_content_policy_under_50_loc() -> None:
    from tests.integration.test_custom_content_policy_only_core_imports import (
        RegexContentPolicy,
    )

    src = inspect.getsource(RegexContentPolicy)
    loc = _count_meaningful_lines(src)
    assert loc < 50, (
        f"RegexContentPolicy is {loc} meaningful LOC; the custom "
        "content-policy example should stay under 50."
    )
