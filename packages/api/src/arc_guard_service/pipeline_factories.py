"""Bundled pipeline factories for service deployments.

These factories are intended for ``ServiceSettings.pipeline_factory``.
They keep the service's global default behavior unchanged while letting
specific deployments opt into richer pipeline wiring.
"""

from __future__ import annotations

from typing import Any, cast

from arc_guard.config_env import GuardConfig
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
from arc_guard.pipeline import GuardPipeline
from arc_guard.reporters.log_reporter import LogReporter
from arc_guard_core.policy import PolicyRule, PolicyRuleSet

from arc_guard_service.observability import StdlibBridgeLogger


def _guardrailflow_dev_policy() -> PolicyRuleSet:
    """Policy-routed baseline for the dockerized dashboard stack.

    The dev stack needs routed outcomes so the dashboard's Policy /
    Decision / Diff surfaces populate during quickstart runs. Keep the
    ruleset intentionally narrow and close to the legacy defaults:
    common PII is redacted, obvious attack signals are blocked.
    """

    return PolicyRuleSet(
        rules=(
            PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
            PolicyRule(id="r_phone", match="PHONE_NUMBER", strategy="redact"),
            PolicyRule(id="r_person", match="PERSON", strategy="redact"),
            PolicyRule(id="r_ssn", match="US_SSN", strategy="redact"),
            PolicyRule(id="r_passport", match="US_PASSPORT", strategy="redact"),
            PolicyRule(id="r_iban", match="IBAN_CODE", strategy="redact"),
            PolicyRule(id="r_ip", match="IP_ADDRESS", strategy="redact"),
            PolicyRule(id="r_card", match="CREDIT_CARD", strategy="redact"),
            PolicyRule(id="r_injection", match="INJECTION", strategy="block"),
            PolicyRule(
                id="r_jailbreak_override",
                match="JAILBREAK_DIRECT_OVERRIDE",
                strategy="block",
            ),
            PolicyRule(
                id="r_jailbreak_ml",
                match="JAILBREAK_ML_DETECTED",
                strategy="block",
            ),
            PolicyRule(
                id="r_policy_violation",
                match="POLICY_VIOLATION",
                strategy="block",
            ),
        )
    )


def guardrailflow_dev_pipeline_factory() -> Any:
    """Build the policy-routed pipeline used by the dockerized dev stack."""

    config = GuardConfig.from_env()
    inspectors = [InjectionInspector(), PresidioInspector(config)]
    return GuardPipeline(
        inspectors=cast(Any, inspectors),
        config=config,
        policy_ruleset=_guardrailflow_dev_policy(),
        reporter=LogReporter(),
        logger_hook=StdlibBridgeLogger(),
    )


__all__ = ["guardrailflow_dev_pipeline_factory"]
