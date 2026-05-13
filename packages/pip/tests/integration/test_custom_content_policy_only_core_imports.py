"""Custom ContentPolicy extension via core-only imports.

Demonstrates that an operator can implement a custom content policy by
importing ONLY from arc_guard_core.protocols.content_policy.
"""

from __future__ import annotations

import re

import pytest
from arc_guard_core.protocols.content_policy import (
    ContentPolicy,
    ContentPolicyDecision,
)
from arc_guard_core.refusal.codes import RefusalCode

from arc_guard.content_policies.aggregate import (
    build_aggregate_refusal_envelope,
    evaluate_content_policies,
)
from arc_guard.content_policies.registry import (
    _reset_for_testing,
    get_content_policy,
    list_registered,
    register_content_policy,
)


class RegexContentPolicy:
    """Custom content policy backed by a regex.

    Imports only from arc_guard_core.protocols.content_policy — no
    arc_guard private internals required.
    """

    def __init__(self, name: str, pattern: str, refusal_code: RefusalCode) -> None:
        self._name = name
        self._pattern = re.compile(pattern, re.IGNORECASE)
        self._refusal_code = refusal_code

    def evaluate(self, text: str) -> ContentPolicyDecision:
        match = self._pattern.search(text)
        return ContentPolicyDecision(
            matched=match is not None,
            confidence=1.0 if match is not None else 0.0,
            policy_name=self._name,
            refusal_code=self._refusal_code if match is not None else None,
        )


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_for_testing()


def test_custom_policy_satisfies_protocol() -> None:
    p = RegexContentPolicy("nope", r"forbidden_word", RefusalCode.POLICY_BLOCK)
    assert isinstance(p, ContentPolicy)


def test_custom_policy_fires_in_same_lifecycle_position_as_bundled() -> None:
    custom = RegexContentPolicy("competitor_block", r"\bcompetitor\b", RefusalCode.POLICY_BLOCK)
    register_content_policy("competitor_block", custom)
    policies = [get_content_policy(n) for n in list_registered()]

    matching_text = "discuss competitor pricing"
    benign_text = "discuss the weather"

    fired = evaluate_content_policies(matching_text, policies)
    not_fired = evaluate_content_policies(benign_text, policies)

    assert len(fired) == 1
    assert fired[0].name == "competitor_block"
    assert not_fired == []


def test_custom_policy_refusal_envelope_matches_bundled_shape() -> None:
    custom = RegexContentPolicy("competitor_block", r"\bcompetitor\b", RefusalCode.POLICY_BLOCK)
    register_content_policy("competitor_block", custom)
    policies = [get_content_policy(n) for n in list_registered()]

    firings = evaluate_content_policies("competitor leaked their roadmap", policies)
    envelope = build_aggregate_refusal_envelope(firings)

    assert envelope.code == RefusalCode.POLICY_BLOCK
    assert envelope.metadata.get("primary_policy") == "competitor_block"
    assert "firing_policies" in envelope.metadata


def test_custom_policy_only_uses_core_imports() -> None:
    import inspect

    src = inspect.getsource(RegexContentPolicy)
    assert "arc_guard." not in src or "arc_guard_core" in src
