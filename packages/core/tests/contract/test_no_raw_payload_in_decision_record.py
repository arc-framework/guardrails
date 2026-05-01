"""DecisionRecord MUST NOT leak raw sensitive payloads.

Per every emitted DecisionRecord serialized to JSON must contain
no substring of the original input of length >= 8 and no portion of any
raw entity content. This test runs the pipeline against a fixture set and
scans serialized records for forbidden substrings.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json

import pytest
from arc_guard.pipeline import GuardPipeline

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardInput, GuardResult, RiskLevel


class _StubInspector:
    name = "stub"

    def __init__(self, findings: tuple[Finding, ...]) -> None:
        self._findings = findings

    async def inspect(self, result: GuardResult) -> GuardResult:
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(result.findings) + self._findings,
            phase=result.phase,
        )


def _f(et: str, start: int, end: int, risk: RiskLevel = RiskLevel.MEDIUM) -> Finding:
    return Finding(et, start, end, risk, "stub")


# Fixture inputs containing distinct PII / PCI / enterprise entities.
FIXTURES: tuple[tuple[str, tuple[Finding, ...]], ...] = (
    (
        "Email Alice Johnson at alice@acme.com about project Helios",
        (
            _f("EMPLOYEE_NAME", 6, 19, RiskLevel.LOW),
            _f("EMAIL_ADDRESS", 23, 37, RiskLevel.LOW),
            _f("INTERNAL_PROJECT", 52, 58, RiskLevel.LOW),
        ),
    ),
    (
        "Card 4111-1111-1111-1111 expires 12/27",
        (_f("CREDIT_CARD", 5, 24, RiskLevel.MEDIUM),),
    ),
    (
        "SSN 123-45-6789 belongs to Bob Williams",
        (
            _f("US_SSN", 4, 15, RiskLevel.HIGH),
            _f("EMPLOYEE_NAME", 27, 39, RiskLevel.LOW),
        ),
    ),
)


def _build_default_policy() -> PolicyRuleSet:
    return PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="hash"),
            PolicyRule(id="r_ssn", match="US_SSN", strategy="redact"),
            PolicyRule(id="r_emp", match="EMPLOYEE_NAME", strategy="redact"),
            PolicyRule(id="r_proj", match="INTERNAL_PROJECT", strategy="redact"),
        ),
    )


def _all_substrings_min_len(text: str, min_len: int = 8) -> set[str]:
    out: set[str] = set()
    for length in range(min_len, len(text) + 1):
        for start in range(len(text) - length + 1):
            out.add(text[start : start + length])
    return out


@pytest.mark.parametrize(("text", "findings"), FIXTURES)
def test_decision_record_does_not_leak_raw_payload(
    text: str, findings: tuple[Finding, ...]
) -> None:
    pipeline = GuardPipeline(
        policy_ruleset=_build_default_policy(),
        inspectors=[_StubInspector(findings)],
    )
    asyncio.run(pipeline.pre_process(GuardInput(text=text)))
    record = pipeline._last_decision
    assert record is not None
    serialized = json.dumps(dataclasses.asdict(record), default=str)

    # Forbidden substring 1: any substring of the original input >= 8 chars
    forbidden = _all_substrings_min_len(text, min_len=8)
    leaked_input = [s for s in forbidden if s in serialized]
    assert leaked_input == [], (
        f"DecisionRecord leaks input substring(s) {leaked_input[:3]!r}"
    )

    # Forbidden substring 2: each raw entity content
    raw_entities = [text[f.start : f.end] for f in findings]
    leaked_entities = [
        raw for raw in raw_entities if len(raw) >= 4 and raw in serialized
    ]
    assert leaked_entities == [], (
        f"DecisionRecord leaks raw entity content {leaked_entities!r}"
    )


def test_decision_record_findings_are_span_only() -> None:
    """Spot-check the FindingSummary shape — no `text` or `original` field."""
    text, findings = FIXTURES[0]
    pipeline = GuardPipeline(
        policy_ruleset=_build_default_policy(),
        inspectors=[_StubInspector(findings)],
    )
    asyncio.run(pipeline.pre_process(GuardInput(text=text)))
    record = pipeline._last_decision
    assert record is not None
    for fs in record.findings:
        # The dataclass field set is the contract — no `text` / `raw` / `value`.
        for forbidden_field in ("text", "raw", "value", "content"):
            assert not hasattr(fs, forbidden_field), (
                f"FindingSummary must not expose {forbidden_field!r}"
            )
