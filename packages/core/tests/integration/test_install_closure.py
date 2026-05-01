"""Integration test for US1 — `core` install closure (T036).

After importing arc_guard_core, no provider SDK module may be present in
sys.modules. This is the runtime sibling of tools/check_dependency_tree.py.
"""

from __future__ import annotations

import sys

import arc_guard_core  # noqa: F401

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
    loaded = FORBIDDEN & set(sys.modules)
    assert loaded == set(), f"forbidden modules loaded by arc_guard_core: {loaded}"


def test_core_pipeline_runs_without_extras() -> None:
    from arc_guard_core import GuardConfig, GuardInput, GuardPipeline

    pipeline = GuardPipeline(config=GuardConfig())
    result = pipeline.pre_process_sync(GuardInput(text="hello"))
    assert result.action == "pass"
    assert result.is_clean
