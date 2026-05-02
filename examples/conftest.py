"""Shared pytest configuration for the example smoke tests.

Each example lives in its own directory with its own ``tests/`` folder.
``--import-mode=importlib`` keeps pytest from treating same-named files
across examples as conflicting module names.
"""

from __future__ import annotations


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Tag every example test with the ``examples`` marker."""
    for item in items:
        item.add_marker("examples")
