"""Custom ContentPolicy implementations participate identically.

Validates that a regex-based custom policy plugged into the content
policy registry fires through the same aggregate-evaluation helper
used by the bundled ``SemanticContentPolicy``, with the resulting
refusal envelope shape matching the bundled-policy case.
"""

from __future__ import annotations

import re

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
    register_content_policy,
)


class RegexContentPolicy:
    """Custom ContentPolicy: matches when ``pattern`` is found in ``text``.

    Operator-side example of the Protocol surface — depends only on
    ``arc_guard_core.protocols.content_policy``, not on any
    ``arc_guard`` private internals.
    """

    def __init__(
        self,
        *,
        name: str,
        pattern: str,
        refusal_code: RefusalCode = RefusalCode.POLICY_BLOCK,
    ) -> None:
        self.name = name
        self._pattern = re.compile(pattern, re.IGNORECASE)
        self._refusal_code = refusal_code

    def evaluate(self, text: str) -> ContentPolicyDecision:
        match = self._pattern.search(text)
        if match is None:
            return ContentPolicyDecision(matched=False, policy_name=self.name)
        return ContentPolicyDecision(
            matched=True,
            confidence=1.0,
            policy_name=self.name,
            refusal_code=self._refusal_code,
        )


def test_custom_content_policy_satisfies_protocol() -> None:
    policy = RegexContentPolicy(
        name="banned_words",
        pattern=r"\bsecret\b",
    )
    assert isinstance(policy, ContentPolicy)


def test_custom_policy_registered_in_registry() -> None:
    _reset_for_testing()
    policy = RegexContentPolicy(
        name="banned_words",
        pattern=r"\bsecret\b",
    )
    register_content_policy("banned_words", policy)
    fetched = get_content_policy("banned_words")
    assert fetched is policy


def test_custom_policy_fires_in_aggregate_lifecycle_position() -> None:
    _reset_for_testing()
    policy = RegexContentPolicy(
        name="banned_words",
        pattern=r"\bsecret\b",
    )
    register_content_policy("banned_words", policy)

    firings = evaluate_content_policies(
        "this contains the secret keyword",
        [policy],
    )
    assert len(firings) == 1
    assert firings[0].name == "banned_words"
    assert firings[0].decision.matched is True


def test_custom_policy_envelope_shape_matches_bundled_case() -> None:
    _reset_for_testing()
    policy = RegexContentPolicy(
        name="banned_words",
        pattern=r"\bsecret\b",
    )
    register_content_policy("banned_words", policy)

    firings = evaluate_content_policies(
        "this contains the secret keyword",
        [policy],
    )
    envelope = build_aggregate_refusal_envelope(firings)
    assert envelope.code == RefusalCode.POLICY_BLOCK.value
    assert envelope.policy == "banned_words"
    assert envelope.metadata["primary_policy"] == "banned_words"
    assert envelope.metadata["firing_policies"][0]["name"] == "banned_words"
    assert envelope.trigger == "content_policy"


def test_custom_policy_below_match_returns_no_firings() -> None:
    _reset_for_testing()
    policy = RegexContentPolicy(
        name="banned_words",
        pattern=r"\bsecret\b",
    )
    register_content_policy("banned_words", policy)

    firings = evaluate_content_policies(
        "this is plain text",
        [policy],
    )
    assert firings == []


def test_custom_policy_with_custom_refusal_code_propagates() -> None:
    _reset_for_testing()
    policy = RegexContentPolicy(
        name="pii_topic",
        pattern=r"\bssn\b",
        refusal_code=RefusalCode.PII_CRITICAL,
    )
    register_content_policy("pii_topic", policy)

    firings = evaluate_content_policies(
        "do you remember my ssn",
        [policy],
    )
    envelope = build_aggregate_refusal_envelope(firings)
    assert envelope.code == RefusalCode.PII_CRITICAL.value
