"""Contract: GuardPipeline() with no `lifecycle_hook=` argument uses
`NullLifecycleSink` and behaves identically to pre-feature behavior on
pre_process / post_process calls.
"""

from __future__ import annotations

import asyncio

from arc_guard.pipeline import GuardPipeline
from arc_guard_core.lifecycle import NullLifecycleSink
from arc_guard_core.types import GuardInput


def test_default_lifecycle_hook_is_null_sink() -> None:
    p = GuardPipeline()
    assert isinstance(p._lifecycle_hook, NullLifecycleSink)


def test_default_pre_process_returns_clean_pass() -> None:
    """Snapshot the default pre_process behavior — it must not change shape now
    that we've added the lifecycle_hook plumbing.
    """
    p = GuardPipeline()
    result = asyncio.run(p.pre_process(GuardInput(text="What is 2 + 2?")))
    assert result.action == "pass"
    assert len(result.findings) == 0


def test_explicit_null_lifecycle_hook_works() -> None:
    p = GuardPipeline(lifecycle_hook=NullLifecycleSink())
    result = asyncio.run(p.pre_process(GuardInput(text="hello")))
    assert result.action == "pass"
