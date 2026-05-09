"""Smoke test that arc_guard_service installs and imports cleanly."""

from __future__ import annotations

import sys


def test_package_imports() -> None:
    import arc_guard_service  # noqa: F401
    import arc_guard_service.settings  # noqa: F401
    import arc_guard_service.validators  # noqa: F401
    from arc_guard_service._placeholder import HANDOFF_NOTE

    assert "future" in HANDOFF_NOTE.lower()
    assert hasattr(arc_guard_service, "__version__")


def test_api_does_not_pull_extra_provider_deps_beyond_pip() -> None:
    """arc_guard_service may transitively pull what arc-guard pulls (e.g.
    presidio), but it MUST NOT pull anything its own dependencies don't
    require — fastapi, uvicorn, etc. are gated behind the [fastapi] extra.

    Runs in a subprocess so the assertion holds regardless of what other
    tests in the same session have already imported.
    """
    import subprocess
    import textwrap

    script = textwrap.dedent(
        """
        import sys

        import arc_guard_service  # noqa: F401
        import arc_guard_service.settings  # noqa: F401
        import arc_guard_service.validators  # noqa: F401

        forbidden_default = {"fastapi", "uvicorn"}
        loaded = forbidden_default & set(sys.modules)
        if loaded:
            raise SystemExit(f"default install pulled: {loaded}")
        """,
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"default-install isolation failed:\n{result.stdout}\n{result.stderr}"
    )
