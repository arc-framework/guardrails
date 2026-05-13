"""Refusal-template registry.

Maps each ``RefusalCode`` to a default ``RefusalTemplate``. Per-rule
overrides take precedence at build time; the registry provides the
fallback.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from arc_guard_core.refusal.codes import RefusalCode

_LOCK = threading.RLock()


@dataclass(frozen=True)
class RefusalTemplate:
    human_message: str
    next_steps: tuple[str, ...]


DEFAULT_REFUSAL_TEMPLATES: dict[RefusalCode, RefusalTemplate] = {
    RefusalCode.JAILBREAK: RefusalTemplate(
        human_message=(
            "This request was blocked because it appeared to attempt jailbreaking the system."
        ),
        next_steps=("Rephrase without language that asks the assistant to ignore its rules.",),
    ),
    RefusalCode.JAILBREAK_STRONG: RefusalTemplate(
        human_message=(
            "This request was blocked because the extended jailbreak detector "
            "identified one or more attack patterns (role-play coercion, "
            "hypothetical framing, policy erosion, or override instructions)."
        ),
        next_steps=(
            "Rephrase the question directly without role-play or hypothetical framing.",
            "Avoid instructions that ask the assistant to ignore its rules.",
        ),
    ),
    RefusalCode.DECEPTION_DRIFT: RefusalTemplate(
        human_message=(
            "This request was blocked because the conversation showed a pattern "
            "of escalating role-play, accumulating exception requests, or "
            "references to forbidden actions discussed earlier."
        ),
        next_steps=(
            "Start a fresh conversation and rephrase the original intent directly.",
            "Avoid framing that references past role-play or 'we already agreed'.",
        ),
    ),
    RefusalCode.PII_CRITICAL: RefusalTemplate(
        human_message=(
            "This request contained sensitive personal information that cannot be processed."
        ),
        next_steps=(
            "Remove personally identifying details before re-submitting.",
            "Use a placeholder description instead of real names or numbers.",
        ),
    ),
    RefusalCode.STRATEGY_FAILED: RefusalTemplate(
        human_message=(
            "An internal processing step failed; the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists.",
        ),
    ),
    RefusalCode.POLICY_BLOCK: RefusalTemplate(
        human_message="This request was blocked by policy.",
        next_steps=("Adjust the request and try again.",),
    ),
    RefusalCode.FIDELITY_DROP: RefusalTemplate(
        human_message=(
            "The model's answer no longer addressed the original request closely "
            "enough to be returned safely; the response was withheld."
        ),
        next_steps=(
            "Rephrase the question more directly.",
            "Split a multi-part request into separate, focused questions.",
            "Simplify or narrow the prompt's scope.",
        ),
    ),
    RefusalCode.API_INVALID_REQUEST: RefusalTemplate(
        human_message="The request payload was rejected at the API boundary.",
        next_steps=(
            "Re-check the request schema against the documented contract.",
            "Verify all required fields are present and well-typed.",
        ),
    ),
    RefusalCode.API_TRANSPORT_TIMEOUT: RefusalTemplate(
        human_message=("The request took longer than the configured maximum and was cancelled."),
        next_steps=(
            "Retry with a smaller payload.",
            "Increase the service's request_timeout_seconds setting.",
        ),
    ),
    RefusalCode.INTERNAL_PIPELINE_ERROR: RefusalTemplate(
        human_message=(
            "An internal pipeline-contract violation was detected; "
            "the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists; reference the correlation_id.",
        ),
    ),
    RefusalCode.INTERNAL_ADAPTER_ERROR: RefusalTemplate(
        human_message=(
            "An adapter boundary validation failed; the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists; reference the correlation_id.",
        ),
    ),
    RefusalCode.INTERNAL_REFUSAL_BUILD_ERROR: RefusalTemplate(
        human_message=(
            "The refusal envelope could not be constructed; "
            "the request was blocked as a safety measure."
        ),
        next_steps=("Contact support; reference the correlation_id.",),
    ),
    RefusalCode.INTERNAL_ENTITY_PROVIDER_ERROR: RefusalTemplate(
        human_message=(
            "An entity-provider operation failed; the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists; reference the correlation_id.",
        ),
    ),
    RefusalCode.INTERNAL_UNKNOWN_ERROR: RefusalTemplate(
        human_message=(
            "An unexpected internal error occurred; the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists; reference the correlation_id.",
        ),
    ),
    RefusalCode.SQL_INJECTION: RefusalTemplate(
        human_message=(
            "The response was blocked because it contained SQL constructs "
            "that could be executed by a downstream database tool."
        ),
        next_steps=(
            "Sanitize generated SQL before passing it to query execution.",
            "Use parameterized queries for any dynamic values.",
        ),
    ),
    RefusalCode.SHELL_INJECTION: RefusalTemplate(
        human_message=(
            "The response was blocked because it contained shell constructs "
            "that could be executed by a downstream tool."
        ),
        next_steps=(
            "Avoid passing model-generated text directly to shell execution.",
            "Use argument-array invocation (subprocess.run([...])) rather than shell=True.",
        ),
    ),
    RefusalCode.TEMPLATE_INJECTION: RefusalTemplate(
        human_message=(
            "The response was blocked because it contained template-engine "
            "constructs that could escape sandboxed rendering."
        ),
        next_steps=(
            "Render model output through a sandboxed template engine with safe-mode enabled.",
            "Escape model output before inclusion in HTML or template contexts.",
        ),
    ),
}


_REGISTRY: dict[RefusalCode, RefusalTemplate] = dict(DEFAULT_REFUSAL_TEMPLATES)


def register_refusal_template(code: RefusalCode, template: RefusalTemplate) -> None:
    with _LOCK:
        _REGISTRY[code] = template


def get_refusal_template(code: RefusalCode) -> RefusalTemplate:
    with _LOCK:
        return _REGISTRY[code]


__all__ = [
    "RefusalTemplate",
    "DEFAULT_REFUSAL_TEMPLATES",
    "register_refusal_template",
    "get_refusal_template",
]
