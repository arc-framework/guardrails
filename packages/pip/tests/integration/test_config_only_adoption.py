"""Adopting all three new capabilities should require zero operator code
beyond standard registry calls and the constructor invocation.

The framework's promise is that policy-file edits + a small Python
registration block are sufficient — no monkey-patching, no subclassing,
no inheriting from arc_guard private internals.
"""

from __future__ import annotations

import inspect

import pytest
from arc_guard_core.policy import PolicyRule
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.content_policies.aggregate import evaluate_content_policies
from arc_guard.content_policies.registry import (
    _reset_for_testing as _reset_cp,
)
from arc_guard.content_policies.registry import (
    get_content_policy,
    list_registered,
    register_content_policy,
)
from arc_guard.content_policies.semantic import SemanticContentPolicy
from arc_guard.inspectors.code_injection import SqlInjectionInspector
from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.registry import _reset_for_testing as _reset_sel


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_sel()
    _reset_cp()


class _StubEncoder:
    encoder_id = "stub:1"

    def encode(self, text: str):  # type: ignore[no-untyped-def]
        return [1.0, 0.0, 0.0]


def _operator_setup_block() -> None:
    """The full operator-supplied setup, fitting under a tight LOC budget."""
    # Selector-driven masking: the "default" selector is auto-registered on
    # import of arc_guard.selectors. No operator code here; just use
    # `selector: default` in YAML.

    register_content_policy(
        "competitor_pricing",
        SemanticContentPolicy(
            name="competitor_pricing",
            exemplars=("competitor pricing", "vendor cost comparison"),
            similarity_threshold=0.78,
            encoder=_StubEncoder(),
        ),
    )


def test_config_only_adoption_yields_working_pipeline() -> None:
    _operator_setup_block()

    sql_inspector = SqlInjectionInspector()
    assert sql_inspector is not None

    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r1", match="EMAIL_ADDRESS", selector="default")
    finding = Finding(
        entity_type="EMAIL_ADDRESS",
        start=0,
        end=10,
        risk_level=RiskLevel.MEDIUM,
        inspector="presidio",
    )
    result = GuardResult(text="me@example.com", action="pass", findings=(finding,))
    name = router._resolve_strategy_name(rule, finding, result)
    assert name == "redact"

    policies = [get_content_policy(n) for n in list_registered()]
    firings = evaluate_content_policies("anything", policies)
    assert isinstance(firings, list)


def test_operator_setup_block_stays_compact() -> None:
    """The full setup block above must fit comfortably under 50 LOC."""
    src = inspect.getsource(_operator_setup_block)
    meaningful = sum(
        1 for line in src.splitlines() if line.strip() and not line.strip().startswith("#")
    )
    assert meaningful < 50, f"_operator_setup_block is {meaningful} meaningful LOC"
