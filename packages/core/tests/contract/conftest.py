"""Pytest hooks for the contract test suite.

Adds ``--update-snapshot`` to write the live public surface back to the
baseline files. Use after intentional additive changes; review the
diff before committing.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshot",
        action="store_true",
        default=False,
        help="Write the live public-surface snapshot to the baseline files.",
    )


@pytest.fixture
def update_snapshot(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-snapshot"))
