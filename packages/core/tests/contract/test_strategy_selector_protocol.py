"""Contract test: StrategySelector Protocol shape.

Verifies the Protocol is runtime_checkable, exposes the documented signature,
and that a minimal implementation satisfies isinstance checks.
"""

from __future__ import annotations

from arc_guard_core.protocols import StrategySelector
from arc_guard_core.types import Finding, GuardResult, RiskLevel


class _MinimalSelector:
    """Smallest possible StrategySelector implementation."""

    def select(self, finding: Finding, guard_result: GuardResult) -> str:
        return "redact"


def test_protocol_is_runtime_checkable() -> None:
    impl = _MinimalSelector()
    assert isinstance(impl, StrategySelector)


def test_minimal_implementation_returns_strategy_name() -> None:
    impl = _MinimalSelector()
    finding = Finding(
        entity_type="EMAIL_ADDRESS",
        start=0,
        end=5,
        risk_level=RiskLevel.MEDIUM,
        inspector="presidio",
    )
    result = GuardResult(text="hello world", action="pass", findings=(finding,))
    assert impl.select(finding, result) == "redact"


def test_non_implementation_fails_isinstance() -> None:
    class _NotASelector:
        # Missing select() method — doesn't conform.
        pass

    assert not isinstance(_NotASelector(), StrategySelector)
