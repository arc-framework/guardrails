"""RuleBasedPolicyRouter — default PolicyRouter implementation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Literal

from arc_guard_core.exceptions import PolicyRouterError
from arc_guard_core.policy import (
    PolicyRule,
    PolicyRuleSet,
    RiskBand,
    RoutedOutcome,
    TransformSummary,
)
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import Finding, GuardResult, PolicyDecision

from arc_guard.policy.aggregation import aggregate_action_for_band
from arc_guard.policy.clarification import build_clarification
from arc_guard.policy.classifier import RiskClassifier, is_ambiguous
from arc_guard.policy.conflict import resolve_conflict
from arc_guard.refusal.builder import RefusalBuilder
from arc_guard.strategies.registry import get_strategy

logger = logging.getLogger("arc_guard")


class RuleBasedPolicyRouter:
    """Resolves rules per finding, applies strategies, builds the outcome.

    Concurrency: sync; thread-safe (all per-call state lives on the stack).
    Failure mode: closed — internal exceptions are wrapped into
    ``PolicyRouterError``; the pipeline converts that into a refusal envelope.
    """

    def __init__(
        self,
        *,
        classifier: RiskClassifier | None = None,
        refusal_builder: RefusalBuilder | None = None,
    ) -> None:
        self._classifier = classifier or RiskClassifier()
        self._refusal_builder = refusal_builder or RefusalBuilder()

    def route(self, result: GuardResult, ruleset: PolicyRuleSet) -> RoutedOutcome:
        try:
            return self._route(result, ruleset)
        except PolicyRouterError:
            raise
        except Exception as exc:  # pragma: no cover (sanity net)
            raise PolicyRouterError(
                f"policy router failure: {exc}",
                code="router.no_decision",
                cause=exc,
            ) from exc

    # --- internal -----------------------------------------------------------

    def _route(self, result: GuardResult, ruleset: PolicyRuleSet) -> RoutedOutcome:
        findings = result.findings

        # Empty findings → trivial pass-through outcome.
        if not findings:
            return RoutedOutcome(
                transformed_text=result.text,
                decisions=(),
                aggregate_action=(
                    "pass"
                    if ruleset.default_action_when_no_rules_fire == "pass"
                    else "block"
                ),
                aggregate_band=RiskBand.LOW,
                refusal=None,
                clarification=None,
                fired_rule_ids=(),
                transforms=(),
            )

        # Per-finding rule resolution
        decisions: list[PolicyDecision] = []
        fired_rule_ids: list[str] = []
        per_finding_winning_rule: dict[int, PolicyRule] = {}

        for finding_idx, finding in enumerate(findings):
            candidates = [
                rule
                for rule in ruleset.rules
                if rule.match == finding.entity_type
                and finding.risk_level >= rule.severity_floor
            ]
            if not candidates:
                continue
            winner, losers = resolve_conflict(candidates)
            per_finding_winning_rule[finding_idx] = winner
            fired_rule_ids.append(winner.id)
            rationale = winner.rationale_template or f"applied {winner.strategy}"
            if losers:
                loser_ids = ", ".join(f"{lr.id}({lr.strategy})" for lr in losers)
                rationale = (
                    f"{rationale} | rule {winner.id}({winner.strategy}) "
                    f"overrode {loser_ids}"
                )
            decisions.append(
                PolicyDecision(
                    finding_ids=(finding_idx,),
                    strategy=winner.strategy,
                    severity=finding.risk_level,
                    rationale=rationale,
                    metadata={"firing_rule_id": winner.id},
                )
            )

        # Aggregate band classification
        band, agg_marker = self._classifier.classify(findings, ruleset.risk_thresholds)
        if agg_marker and decisions:
            # When a count-based aggregation rule (e.g. soft-PII escalation)
            # changed the band, record that in the leading decision so the
            # audit trail explains why the band differs from per-finding
            # severities.
            first = decisions[0]
            decisions[0] = PolicyDecision(
                finding_ids=first.finding_ids,
                strategy=first.strategy,
                severity=first.severity,
                rationale=f"{first.rationale} | {agg_marker}",
                metadata=first.metadata,
            )

        # Apply strategies to produce transformed text + transform summaries.
        transformed_text, transforms = self._apply_strategies(
            result.text, findings, decisions, per_finding_winning_rule
        )

        # Aggregate action selection driven by the run's risk band.
        aggregate_action = aggregate_action_for_band(band, decisions)

        # Refusal + clarification policy
        refusal = None
        clarification = None
        if is_ambiguous(band, ruleset):
            firing = self._highest_severity_rule(per_finding_winning_rule, findings)
            clarification = build_clarification(firing, findings)
            # Clarification path overrides any refusal envelope; action stays "pass".
            aggregate_action = "pass"
        elif band in (RiskBand.HIGH, RiskBand.CRITICAL):
            firing = self._highest_severity_rule(per_finding_winning_rule, findings)
            if firing is None and ruleset.rules:
                firing = ruleset.rules[0]
            if firing is not None:
                code = self._select_refusal_code(findings)
                refusal = self._refusal_builder.build(
                    firing_rule=firing,
                    decisions=decisions,
                    code=code,
                    trigger=findings[0].entity_type if findings else "policy",
                    policy_id=firing.id,
                )
        # CRITICAL band: blank the text and force the block action.
        # The refusal envelope above carries the user-facing explanation.
        if band == RiskBand.CRITICAL:
            transformed_text = ""
            aggregate_action = "block"

        return RoutedOutcome(
            transformed_text=transformed_text,
            decisions=tuple(decisions),
            aggregate_action=aggregate_action,
            aggregate_band=band,
            refusal=refusal,
            clarification=clarification,
            fired_rule_ids=tuple(fired_rule_ids),
            transforms=transforms,
        )

    # --- helpers ------------------------------------------------------------

    def _apply_strategies(
        self,
        text: str,
        findings: Sequence[Finding],
        decisions: Sequence[PolicyDecision],
        per_finding_rule: dict[int, PolicyRule],
    ) -> tuple[str, tuple[TransformSummary, ...]]:
        """Apply each finding's chosen strategy in span order.

        Strategies that operate on individual spans (redact, hash, tokenize)
        contribute their replacements; ``warn`` is pass-through; ``block``
        is handled at the run level (text emptied for CRITICAL).
        """
        # Group findings by strategy name so we can call each strategy once
        # over its own subset of findings. This preserves each strategy's
        # internal numbering (e.g. redact's per-type counters).
        per_strategy: dict[str, list[int]] = {}
        for d in decisions:
            per_strategy.setdefault(d.strategy, []).extend(d.finding_ids)

        # Build replacements list: (start, end, replacement, finding_idx, strategy)
        replacements: list[tuple[int, int, str, int, str]] = []

        for strategy_name, finding_indices in per_strategy.items():
            if strategy_name in ("block", "warn", "pass"):
                # block / warn / pass do not transform individual spans here.
                continue
            try:
                strategy = get_strategy(strategy_name)
            except Exception:
                # Unknown strategy: pipeline-level validation should have caught this.
                continue
            subset = tuple(findings[i] for i in finding_indices)
            sub_text = text  # Pass the full original text; the strategy uses span offsets.
            try:
                transformed_sub, _sub_decisions = strategy.apply(sub_text, subset)
            except Exception as exc:
                logger.warning(
                    "strategy %r failed during routing: %s — skipping",
                    strategy_name,
                    exc,
                )
                continue
            # Re-derive each finding's replacement by diffing.
            for idx, fi in enumerate(finding_indices):
                f = findings[fi]
                # Find the corresponding span in the transformed text by
                # comparing original spans. For redact / tokenize / hash,
                # the strategy applied right-to-left so we walk from the
                # end of the original text to find the replacement.
                # Simpler approach: ask the strategy to give us the
                # placeholder via metadata in the decision they returned.
                # We have it: _sub_decisions correspond to subset in the
                # strategy's output order.
                if idx < len(_sub_decisions):
                    sub_dec = _sub_decisions[idx]
                    placeholder = sub_dec.metadata.get(
                        "placeholder",
                        sub_dec.metadata.get("replacement", sub_dec.metadata.get("token", "")),
                    )
                else:
                    placeholder = ""
                replacements.append(
                    (f.start, f.end, str(placeholder), fi, strategy_name)
                )

        # Apply right-to-left so offsets stay stable
        out = text
        for start, end, replacement, _fi, _sname in sorted(
            replacements, key=lambda r: -r[0]
        ):
            out = out[:start] + replacement + out[end:]

        # Build TransformSummary tuple in finding-index order
        transforms: list[TransformSummary] = []
        replacements_by_idx = {r[3]: r for r in replacements}
        for fi, _f in enumerate(findings):
            if fi in replacements_by_idx:
                start, end, replacement, _, sname = replacements_by_idx[fi]
                kind = _replacement_kind(sname, replacement)
                transforms.append(
                    TransformSummary(
                        strategy=sname,
                        target_finding_index=fi,
                        before_length=end - start,
                        after_length=len(replacement),
                        replacement_kind=kind,
                        metadata={"replacement": replacement},
                    )
                )
            else:
                # Find the strategy applied (for warn / block findings)
                matched = next((d for d in decisions if fi in d.finding_ids), None)
                if matched is None:
                    continue
                kind = _replacement_kind(matched.strategy, "")
                transforms.append(
                    TransformSummary(
                        strategy=matched.strategy,
                        target_finding_index=fi,
                        before_length=findings[fi].end - findings[fi].start,
                        after_length=findings[fi].end - findings[fi].start,
                        replacement_kind=kind,
                        metadata={},
                    )
                )

        return out, tuple(transforms)

    def _highest_severity_rule(
        self, per_finding: dict[int, PolicyRule], findings: Sequence[Finding]
    ) -> PolicyRule | None:
        if not per_finding:
            return None
        # Pick the rule attached to the highest-severity finding
        sorted_items = sorted(
            per_finding.items(),
            key=lambda kv: -int(findings[kv[0]].risk_level),
        )
        return sorted_items[0][1]

    def _select_refusal_code(self, findings: Sequence[Finding]) -> RefusalCode:
        types = {f.entity_type.upper() for f in findings}
        if "INJECTION" in types or "JAILBREAK" in types:
            return RefusalCode.JAILBREAK
        if any(t in types for t in ("US_SSN", "CREDIT_CARD", "PHONE_NUMBER")):
            return RefusalCode.PII_CRITICAL
        return RefusalCode.POLICY_BLOCK


def _replacement_kind(
    strategy: str, replacement: str
) -> Literal["placeholder", "hash", "token", "removed", "warn", "passed"]:
    if strategy == "redact":
        return "placeholder"
    if strategy == "hash":
        return "hash"
    if strategy == "tokenize":
        return "token"
    if strategy == "block":
        return "removed"
    if strategy == "warn":
        return "warn"
    return "passed"


__all__ = ["RuleBasedPolicyRouter"]
