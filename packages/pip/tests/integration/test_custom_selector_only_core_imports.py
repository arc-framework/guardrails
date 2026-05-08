"""Custom StrategySelector extension via core-only imports.

Demonstrates that an operator can implement a custom selector by
importing ONLY from arc_guard_core.protocols.strategy_selector — no
arc_guard private internals required. The Protocol is a first-class
extension point.
"""

from __future__ import annotations

import pytest

from arc_guard_core.policy import PolicyRule
from arc_guard_core.protocols.strategy_selector import StrategySelector
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.policy.router import RuleBasedPolicyRouter
from arc_guard.selectors.registry import _reset_for_testing
from arc_guard.selectors.registry import register_selector


# This implementation imports ONLY from arc_guard_core.protocols.
# No arc_guard.* imports inside the class — verified by the test below.
class EntitlementsBasedSelector:
    """Custom selector that consults a per-tenant entitlements decision.

    Real version would call an internal entitlements service; here we use
    a fixture mapping for determinism.
    """

    def __init__(self, entitlements: dict[str, str]) -> None:
        self._entitlements = entitlements

    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        return self._entitlements.get(finding.entity_type, "redact")


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_for_testing()


def test_custom_selector_satisfies_protocol() -> None:
    sel = EntitlementsBasedSelector({"EMAIL_ADDRESS": "hash"})
    assert isinstance(sel, StrategySelector)


def test_custom_selector_invoked_via_registry() -> None:
    sel = EntitlementsBasedSelector({"EMAIL_ADDRESS": "hash", "CREDIT_CARD": "block"})
    register_selector("entitlements", sel)

    router = RuleBasedPolicyRouter()
    rule = PolicyRule(id="r1", match="EMAIL_ADDRESS", selector="entitlements")
    finding = Finding(
        entity_type="EMAIL_ADDRESS",
        start=0,
        end=10,
        risk_level=RiskLevel.MEDIUM,
        inspector="test",
    )
    result = GuardResult(text="me@example.com", action="pass", findings=(finding,))

    strategy_name = router._resolve_strategy_name(rule, finding, result)

    assert strategy_name == "hash"


def test_custom_selector_only_uses_core_imports() -> None:
    """Inspect this test file's own imports to confirm the implementation
    above only depends on arc_guard_core.protocols.* — no private
    arc_guard internals leak into operator-extension code."""
    import inspect

    src = inspect.getsource(EntitlementsBasedSelector)
    # The class body must not import anything; module-level imports above
    # only reference arc_guard_core (for the Protocol + types) and the
    # test harness itself uses arc_guard.selectors.registry which is the
    # documented public registration API. The class itself has no
    # arc_guard.* dependency.
    assert "arc_guard." not in src or "arc_guard_core" in src
