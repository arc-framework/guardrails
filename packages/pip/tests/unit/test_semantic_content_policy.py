"""Construction-time validation for SemanticContentPolicy.

Covers the documented load-time error matrix:
- empty exemplar tuple
- empty exemplar string
- non-string exemplar
- threshold < 0.0
- threshold > 1.0
- empty name
Plus a happy-path construction with a stub encoder (the bundled
encoder requires the optional [semantic] extra which is not installed
in the dev environment).
"""

from __future__ import annotations

from typing import Any

import pytest
from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.refusal.codes import RefusalCode

from arc_guard.content_policies.semantic import SemanticContentPolicy


class _StubEncoder:
    """Returns a fixed vector for any input.

    Acts as a stand-in for the spec-005 intent encoder so unit tests
    don't depend on the optional [semantic] extra. The vector
    dimension must stay constant across calls; otherwise cosine
    similarity comparisons error.
    """

    def __init__(self, vector: list[float] | None = None) -> None:
        self._vector = vector or [1.0, 0.0, 0.0]

    def encode(self, text: str) -> list[float]:
        return list(self._vector)


def test_valid_construction_succeeds() -> None:
    encoder = _StubEncoder()
    policy = SemanticContentPolicy(
        name="competitor_pricing",
        exemplars=("foo", "bar", "baz"),
        similarity_threshold=0.78,
        encoder=encoder,
    )
    assert policy.name == "competitor_pricing"
    assert policy.exemplars == ("foo", "bar", "baz")
    assert policy.similarity_threshold == 0.78
    assert policy.refusal_code == RefusalCode.POLICY_BLOCK
    assert policy._active is True
    assert len(policy._exemplar_encodings) == 3


def test_custom_refusal_code_preserved() -> None:
    policy = SemanticContentPolicy(
        name="x",
        exemplars=("abc",),
        similarity_threshold=0.5,
        refusal_code=RefusalCode.PII_CRITICAL,
        encoder=_StubEncoder(),
    )
    assert policy.refusal_code == RefusalCode.PII_CRITICAL


def test_empty_exemplars_raises() -> None:
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=(),
            similarity_threshold=0.5,
            encoder=_StubEncoder(),
        )
    assert "zero exemplars" in str(excinfo.value)


def test_empty_exemplar_string_raises() -> None:
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=("ok", "", "ok2"),
            similarity_threshold=0.5,
            encoder=_StubEncoder(),
        )
    msg = str(excinfo.value)
    assert "exemplar at index 1" in msg


def test_non_string_exemplar_raises() -> None:
    bad: Any = ("ok", 42)
    with pytest.raises(ConfigSchemaError):
        SemanticContentPolicy(
            name="x",
            exemplars=bad,
            similarity_threshold=0.5,
            encoder=_StubEncoder(),
        )


def test_threshold_below_zero_raises() -> None:
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=("ok",),
            similarity_threshold=-0.1,
            encoder=_StubEncoder(),
        )
    assert "outside [0.0, 1.0]" in str(excinfo.value)


def test_threshold_above_one_raises() -> None:
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=("ok",),
            similarity_threshold=1.1,
            encoder=_StubEncoder(),
        )
    assert "outside [0.0, 1.0]" in str(excinfo.value)


def test_threshold_boundary_zero_accepted() -> None:
    policy = SemanticContentPolicy(
        name="x",
        exemplars=("ok",),
        similarity_threshold=0.0,
        encoder=_StubEncoder(),
    )
    assert policy.similarity_threshold == 0.0


def test_threshold_boundary_one_accepted() -> None:
    policy = SemanticContentPolicy(
        name="x",
        exemplars=("ok",),
        similarity_threshold=1.0,
        encoder=_StubEncoder(),
    )
    assert policy.similarity_threshold == 1.0


def test_empty_name_raises() -> None:
    with pytest.raises(ConfigSchemaError):
        SemanticContentPolicy(
            name="",
            exemplars=("ok",),
            similarity_threshold=0.5,
            encoder=_StubEncoder(),
        )


def test_evaluate_above_threshold_returns_match() -> None:
    encoder = _StubEncoder(vector=[1.0, 0.0, 0.0])
    policy = SemanticContentPolicy(
        name="topic_block",
        exemplars=("anything",),
        similarity_threshold=0.5,
        encoder=encoder,
    )
    decision = policy.evaluate("input text")
    assert decision.matched is True
    assert decision.policy_name == "topic_block"
    assert decision.refusal_code == RefusalCode.POLICY_BLOCK
    assert decision.confidence is not None
    assert decision.confidence >= 0.5


class _DimensionEncoder:
    """Encodes whichever of two strings is supplied with two distinct vectors.

    Lets the test exercise the cosine path so threshold comparison
    actually depends on input identity.
    """

    def __init__(self) -> None:
        self._cache = {
            "exemplar": [1.0, 0.0],
            "similar": [0.99, 0.01],
            "different": [0.0, 1.0],
        }

    def encode(self, text: str) -> list[float]:
        return list(self._cache.get(text, [0.0, 0.0]))


def test_evaluate_below_threshold_returns_no_match() -> None:
    policy = SemanticContentPolicy(
        name="strict",
        exemplars=("exemplar",),
        similarity_threshold=0.9,
        encoder=_DimensionEncoder(),
    )
    decision = policy.evaluate("different")
    assert decision.matched is False
    assert decision.refusal_code is None
    assert decision.policy_name == "strict"


def test_evaluate_close_match_above_threshold() -> None:
    policy = SemanticContentPolicy(
        name="lenient",
        exemplars=("exemplar",),
        similarity_threshold=0.9,
        encoder=_DimensionEncoder(),
    )
    decision = policy.evaluate("similar")
    assert decision.matched is True
    assert decision.confidence is not None
    assert decision.confidence > 0.9
