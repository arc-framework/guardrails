"""Bundled pipeline factories for service deployments.

These factories are intended for ``ServiceSettings.pipeline_factory``.
They keep the service's global default behavior unchanged while letting
specific deployments opt into richer pipeline wiring.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any, cast

from arc_guard.config_env import GuardConfig
from arc_guard.deception.inspector import StatefulConversationInspector
from arc_guard.inspectors.code_injection.shell import ShellInjectionInspector
from arc_guard.inspectors.code_injection.template import TemplateInjectionInspector
from arc_guard.inspectors.injection import InjectionInspector
from arc_guard.inspectors.presidio import PresidioInspector
from arc_guard.jailbreak.detector import RuleBasedJailbreakDetector
from arc_guard.pipeline import GuardPipeline
from arc_guard.reporters.log_reporter import LogReporter
from arc_guard_core.policy import PolicyRule, PolicyRuleSet

from arc_guard_service.observability import StdlibBridgeLogger

_LOG = logging.getLogger(__name__)


def _extra_installed(name: str) -> bool:
    if name == "code-injection":
        return importlib.util.find_spec("sqlparse") is not None
    if name == "semantic":
        return importlib.util.find_spec("sentence_transformers") is not None
    if name == "jailbreak-ml":
        return importlib.util.find_spec("transformers") is not None
    return False


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


def _all_inspectors_policy() -> PolicyRuleSet:
    """Comprehensive ruleset covering every inspector this factory wires.

    Adds policy entries for the semantic-intent inspector's emitted entity
    types so dashboard surfaces (Decision / Policy tabs) reflect why an
    intent-class refusal fired.
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
            PolicyRule(
                id="r_deception",
                match="DECEPTION_DETECTED",
                strategy="block",
            ),
            PolicyRule(
                id="r_jailbreak_intent",
                match="JAILBREAK_INTENT",
                strategy="block",
            ),
        )
    )


def all_inspectors_pipeline_factory(lifecycle_hook: Any | None = None) -> Any:
    """Comprehensive pipeline wiring every inspector whose deps are present.

    Activates: Injection, Presidio (PII), Shell-injection, Template-injection,
    SQL-injection (when ``[code-injection]`` extra installed), SemanticIntent
    (when ``[semantic]`` extra installed), heuristic jailbreak detection,
    and stateful deception scoring. Code-injection inspectors run at both
    pre- and post-process so user input is screened in addition to model
    output. The semantic-intent inspector closes the gap pattern-based
    detectors leave when threats are paraphrased — see
    ``arc_guard.inspectors.semantic_intent`` for category coverage.

    Wire in deployment via ``ServiceSettings.pipeline_factory =
    "arc_guard_service.pipeline_factories.all_inspectors_pipeline_factory"``
    or the ``ARC_GUARD_PIPELINE_FACTORY`` env var.
    """

    config = GuardConfig.from_env()
    both_phases = ("pre_process", "post_process")
    inspectors: list[Any] = [
        InjectionInspector(),
        PresidioInspector(config),
        ShellInjectionInspector(phases=both_phases),
        TemplateInjectionInspector(phases=both_phases),
    ]

    if _extra_installed("code-injection"):
        from arc_guard.inspectors.code_injection.sql import SqlInjectionInspector

        inspectors.append(SqlInjectionInspector(phases=both_phases))
    else:
        _LOG.info("[code-injection] extra not installed — SQL inspector skipped")

    if _extra_installed("semantic"):
        try:
            from arc_guard.inspectors.semantic_intent import SemanticIntentInspector

            inspectors.append(SemanticIntentInspector())
        except Exception as exc:  # pragma: no cover — defensive
            _LOG.warning("SemanticIntentInspector failed to load: %s", exc)
    else:
        _LOG.info("[semantic] extra not installed — semantic intent inspector skipped")

    return GuardPipeline(
        inspectors=cast(Any, inspectors),
        config=config,
        policy_ruleset=_all_inspectors_policy(),
        reporter=LogReporter(),
        logger_hook=StdlibBridgeLogger(),
        jailbreak_detector=RuleBasedJailbreakDetector(),
        conversation_turn_inspector=StatefulConversationInspector(),
        lifecycle_hook=lifecycle_hook,
    )


__all__ = [
    "guardrailflow_dev_pipeline_factory",
    "all_inspectors_pipeline_factory",
]
