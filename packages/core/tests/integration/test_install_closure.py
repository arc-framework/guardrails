"""`core` install closure: zero provider SDK imports.

A fresh Python interpreter that imports only ``arc_guard_core`` must
not pull any provider SDK into ``sys.modules``. We run this in a
subprocess so sibling tests (which legitimately import presidio,
transformers, etc. for inspector tests) cannot pollute the snapshot.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

FORBIDDEN = {
    "presidio_analyzer",
    "presidio_anonymizer",
    "nats",
    "UnleashClient",
    "httpx",
    "opentelemetry",
    "torch",
    "transformers",
    "fastapi",
    "uvicorn",
}


def test_core_import_does_not_pull_provider_modules() -> None:
    code = textwrap.dedent(
        f"""
        import sys
        import arc_guard_core  # noqa: F401

        forbidden = {sorted(FORBIDDEN)!r}
        loaded = [m for m in forbidden if m in sys.modules]
        if loaded:
            raise SystemExit(
                f"forbidden modules loaded by arc_guard_core: {{loaded}}"
            )
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_core_pipeline_runs_without_extras() -> None:
    from arc_guard_core import GuardConfig, GuardInput, GuardPipeline

    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.pre_process_sync(GuardInput(text="hello"))
    assert result.action == "pass"
    assert result.is_clean
