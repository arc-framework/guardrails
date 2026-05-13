"""Custom-strategy integration: third-party strategy works without modifying core."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence

from arc_guard_core.policy import PolicyRule, PolicyRuleSet
from arc_guard_core.types import Finding, GuardInput, GuardResult, PolicyDecision, RiskLevel

from arc_guard.pipeline import GuardPipeline
from arc_guard.strategies.registry import register_strategy


class _TokenizeWithTenantSalt:
    """Quickstart §C — custom tokenizer with a per-tenant secret salt."""

    name = "tokenize_tenant"

    def __init__(self, tenant_secret: str = "test-secret") -> None:
        self._secret = tenant_secret.encode()

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        out = text
        decisions: list[PolicyDecision] = []
        for finding_idx, f in sorted(enumerate(findings), key=lambda pair: -pair[1].start):
            entity = text[f.start : f.end]
            digest = hashlib.sha256(entity.encode() + self._secret).hexdigest()[:8]
            token = f"[{f.entity_type}_TOK_{digest}]"
            out = out[: f.start] + token + out[f.end :]
            decisions.append(
                PolicyDecision(
                    finding_ids=(finding_idx,),
                    strategy=self.name,
                    severity=f.risk_level,
                    rationale=f"tokenized {f.entity_type}",
                    # The router looks up `metadata["token"]` (or "placeholder"
                    # / "replacement") to extract the replacement text when
                    # composing the final transformed text. Custom strategies
                    # MUST set one of these keys so multi-strategy runs can
                    # compose correctly.
                    metadata={"token": token, "digest_prefix": digest},
                )
            )
        return out, tuple(reversed(decisions))


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


_CUSTOM_INSTANCE = _TokenizeWithTenantSalt()
register_strategy("tokenize_tenant", _CUSTOM_INSTANCE)


def test_custom_strategy_registered_and_used_in_policy() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_tokenize_cards",
                match="CREDIT_CARD",
                strategy="tokenize_tenant",
            ),
        ),
    )
    findings = (Finding("CREDIT_CARD", 12, 28, RiskLevel.LOW, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text="My card is 4111111111111111")))
    # Token is in the output.
    assert "[CREDIT_CARD_TOK_" in result.text
    # Decision attribution matches custom strategy name.
    assert result.decisions[0].strategy == "tokenize_tenant"


def test_custom_strategy_decision_attribution() -> None:
    policy = PolicyRuleSet(
        rules=(
            PolicyRule(
                id="r_tokenize",
                match="EMAIL_ADDRESS",
                strategy="tokenize_tenant",
            ),
        ),
    )
    findings = (Finding("EMAIL_ADDRESS", 0, 14, RiskLevel.LOW, "stub"),)
    pipeline = GuardPipeline(
        policy_ruleset=policy,
        inspectors=[_StubInspector(findings)],
    )
    result = asyncio.run(pipeline.pre_process(GuardInput(text="alice@acme.com")))
    assert result.decisions[0].metadata.get("firing_rule_id") == "r_tokenize"
