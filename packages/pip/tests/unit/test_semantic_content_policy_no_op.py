"""Missing-extra behavior — SemanticContentPolicy registers as no-op.

When ``arc_guard.middleware.semantic.encoder`` cannot be imported (the
``[semantic]`` extra is not installed), construction MUST succeed,
``_active`` MUST be False, ``evaluate()`` MUST return a non-matching
decision regardless of input, and the structured warning event MUST be
emitted exactly once via the configured logger.
"""

from __future__ import annotations

import builtins
import sys
from typing import Any

import pytest

from arc_guard.content_policies.semantic import (
    GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT,
    SemanticContentPolicy,
)


class _RecordingLogger:
    """Captures every event emitted via the Logger Protocol."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def bind(self, **fields: Any) -> _RecordingLogger:
        return self

    def event(self, name: str, *, level: str = "info", **fields: Any) -> None:
        self.events.append({"name": name, "level": level, **fields})


@pytest.fixture
def force_missing_semantic_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force ``import arc_guard.middleware.semantic.encoder`` to raise.

    Pops any cached module from ``sys.modules`` so the importer is
    actually invoked, then patches ``builtins.__import__`` to refuse the
    encoder module.
    """
    encoder_modules = [
        "arc_guard.middleware.semantic.encoder",
    ]
    for mod in encoder_modules:
        sys.modules.pop(mod, None)

    real_import = builtins.__import__

    def _faux_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name in encoder_modules or (name.startswith("arc_guard.middleware.semantic.encoder")):
            raise ImportError(f"forced missing: {name}")
        if name == "arc_guard.middleware.semantic.encoder":
            raise ImportError(f"forced missing: {name}")
        if name == "arc_guard.middleware.semantic" and "encoder" in (fromlist or ()):
            raise ImportError("forced missing: arc_guard.middleware.semantic.encoder")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _faux_import)


def test_missing_extra_construction_does_not_raise(
    force_missing_semantic_extra: None,
) -> None:
    logger = _RecordingLogger()
    policy = SemanticContentPolicy(
        name="topic_block",
        exemplars=("anything",),
        similarity_threshold=0.5,
        logger=logger,
    )
    assert policy._active is False


def test_missing_extra_evaluate_always_returns_no_match(
    force_missing_semantic_extra: None,
) -> None:
    logger = _RecordingLogger()
    policy = SemanticContentPolicy(
        name="topic_block",
        exemplars=("anything",),
        similarity_threshold=0.5,
        logger=logger,
    )
    decision = policy.evaluate("any input whatsoever")
    assert decision.matched is False
    assert decision.policy_name == "topic_block"
    assert decision.refusal_code is None


def test_missing_extra_emits_structured_warning_event(
    force_missing_semantic_extra: None,
) -> None:
    logger = _RecordingLogger()
    SemanticContentPolicy(
        name="topic_block",
        exemplars=("anything",),
        similarity_threshold=0.5,
        logger=logger,
    )
    matching = [
        ev
        for ev in logger.events
        if ev["name"] == GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT
    ]
    assert len(matching) == 1
    ev = matching[0]
    assert ev["level"] == "warning"
    assert ev["policy_name"] == "topic_block"
    assert ev["install_hint"] == "pip install arc-guard[semantic]"


def test_missing_extra_event_emitted_exactly_once(
    force_missing_semantic_extra: None,
) -> None:
    logger = _RecordingLogger()
    SemanticContentPolicy(
        name="single_emit",
        exemplars=("anything",),
        similarity_threshold=0.5,
        logger=logger,
    )
    count = sum(
        1 for ev in logger.events if ev["name"] == GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT
    )
    assert count == 1
