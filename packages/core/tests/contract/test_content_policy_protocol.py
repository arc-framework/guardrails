"""Contract test: ContentPolicy Protocol + ContentPolicyDecision shape."""

from __future__ import annotations

from dataclasses import is_dataclass

from arc_guard_core.protocols import ContentPolicy, ContentPolicyDecision
from arc_guard_core.refusal.codes import RefusalCode


class _MinimalContentPolicy:
    def evaluate(self, text: str) -> ContentPolicyDecision:
        return ContentPolicyDecision(matched="block-me" in text, confidence=0.9)


def test_decision_is_frozen_dataclass() -> None:
    assert is_dataclass(ContentPolicyDecision)
    d = ContentPolicyDecision(matched=True, confidence=0.5)
    # Frozen — assignment must raise.
    try:
        d.matched = False  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("ContentPolicyDecision must be frozen")


def test_decision_field_defaults() -> None:
    d = ContentPolicyDecision(matched=False)
    assert d.confidence is None
    assert d.policy_name == ""
    assert d.refusal_code is None


def test_decision_accepts_refusal_code() -> None:
    d = ContentPolicyDecision(
        matched=True, confidence=0.99, policy_name="x", refusal_code=RefusalCode.POLICY_BLOCK
    )
    assert d.refusal_code == RefusalCode.POLICY_BLOCK


def test_protocol_is_runtime_checkable() -> None:
    assert isinstance(_MinimalContentPolicy(), ContentPolicy)


def test_non_implementation_fails_isinstance() -> None:
    class _NotAPolicy:
        pass

    assert not isinstance(_NotAPolicy(), ContentPolicy)


def test_evaluate_returns_decision() -> None:
    p = _MinimalContentPolicy()
    yes = p.evaluate("contains block-me trigger")
    no = p.evaluate("clean text")
    assert yes.matched is True
    assert no.matched is False
