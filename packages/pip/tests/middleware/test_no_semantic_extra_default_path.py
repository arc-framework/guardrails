"""Without the ``[semantic]`` extra installed, the SDK still imports cleanly.

Simulates the missing-extra case via ``sys.modules`` patching so the
test runs even when the extra IS installed in the dev environment.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def test_top_level_factory_import_works_without_semantic_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Importing ``from_sentence_transformers`` from the middleware
    namespace succeeds even with the extra absent."""
    if sys.modules.get("sentence_transformers") is not None:
        pytest.skip(
            "sentence_transformers was imported earlier in this pytest session;"
            " the absent-extra simulation requires subprocess isolation here."
        )
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    monkeypatch.setitem(sys.modules, "numpy", None)
    # Force a fresh import of the middleware module.
    if "arc_guard.middleware" in sys.modules:
        importlib.reload(sys.modules["arc_guard.middleware"])
    from arc_guard.middleware import from_sentence_transformers

    assert callable(from_sentence_transformers)


def test_factory_call_without_extra_raises_friendly_importerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling the factory without the extra raises ImportError with hint."""
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    from arc_guard.middleware import from_sentence_transformers

    with pytest.raises(ImportError, match=r"\[semantic\]"):
        from_sentence_transformers()


def test_default_pipeline_works_without_semantic_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``GuardPipeline()`` with null defaults works regardless of the extra."""
    import asyncio

    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    monkeypatch.setitem(sys.modules, "numpy", None)

    from arc_guard_core.types import GuardInput

    from arc_guard.pipeline import GuardPipeline

    async def _run() -> None:
        pipe = GuardPipeline(inspectors=[])
        result = await pipe.pre_process(GuardInput(text="hello"))
        assert result.action == "pass"
        assert result.fidelity_score is not None
        assert result.fidelity_score.sentinel == "not_measured"

    asyncio.run(_run())
