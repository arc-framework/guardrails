"""Aggregate evaluation across registered ``ContentPolicy`` instances.

The pipeline integration call site is documented at the bottom of this
module. The helper here is fully testable in isolation: tests can
build a list of policy instances, run ``evaluate_content_policies()``,
and assert the resulting decisions and refusal envelope shape without
spinning up ``GuardPipeline``.

When the helper is wired into the pipeline, the integration point sits
between ``sanitize`` and ``route`` — distinct lifecycle position from
``PolicyRule`` evaluation, per the content-policy contract.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from arc_guard_core.protocols.content_policy import (
    ContentPolicy,
    ContentPolicyDecision,
)
from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.types import RefusalEnvelope


@dataclass(frozen=True)
class ContentPolicyFiring:
    """One matched ``ContentPolicy`` decision plus the policy reference.

    The aggregate refusal envelope cites these in order to show
    operators which of multiple content policies a request violated.
    """

    name: str
    decision: ContentPolicyDecision
    exemplar_set_id: str


def exemplar_set_id(exemplars: Sequence[str]) -> str:
    """Stable identifier for an exemplar tuple.

    SHA-256 over the newline-joined UTF-8 bytes, truncated to 16 hex
    chars. The same ordered set always produces the same id; reordering
    the exemplars produces a different id by design (the encoder's
    sensitivity to order is a property worth surfacing).
    """
    payload = "\n".join(exemplars).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _resolve_exemplars(policy: Any) -> tuple[str, ...]:
    """Best-effort lookup of an ``exemplars`` attribute.

    Custom ``ContentPolicy`` implementations are not required to expose
    exemplars (a regex-based custom policy doesn't have any). When the
    attribute is missing, the exemplar-set id falls back to a stable
    digest of the policy's name.
    """
    exemplars = getattr(policy, "exemplars", None)
    if isinstance(exemplars, tuple):
        return exemplars
    if isinstance(exemplars, list):
        return tuple(exemplars)
    return ()


def _resolve_name(policy: ContentPolicy, decision: ContentPolicyDecision) -> str:
    """Pull a stable policy name.

    The decision's ``policy_name`` is canonical when set; else fall back
    to the policy instance's ``name`` attribute, then the type name.
    """
    if decision.policy_name:
        return decision.policy_name
    name = getattr(policy, "name", None)
    if isinstance(name, str) and name:
        return name
    return type(policy).__name__


def evaluate_content_policies(
    text: str,
    policies: Iterable[ContentPolicy],
) -> list[ContentPolicyFiring]:
    """Run every registered content policy against ``text``.

    Returns the list of firings in evaluation order — that order
    determines which policy's ``RefusalCode`` becomes the envelope's
    primary code per the content-policy aggregate-evaluation contract.

    Caller responsibility: emit the matching ``FindingProduced``
    lifecycle event for each firing using the metadata from
    ``build_finding_metadata``. The helper itself is observability-free
    so it can be unit-tested in isolation.
    """
    firings: list[ContentPolicyFiring] = []
    for policy in policies:
        decision = policy.evaluate(text)
        if not decision.matched:
            continue
        name = _resolve_name(policy, decision)
        exemplars = _resolve_exemplars(policy)
        if exemplars:
            digest = exemplar_set_id(exemplars)
        else:
            digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        firings.append(
            ContentPolicyFiring(
                name=name,
                decision=ContentPolicyDecision(
                    matched=True,
                    confidence=decision.confidence,
                    policy_name=name,
                    refusal_code=decision.refusal_code,
                ),
                exemplar_set_id=digest,
            ),
        )
    return firings


def build_finding_metadata(firing: ContentPolicyFiring) -> dict[str, Any]:
    """Metadata for a content-policy ``FindingProduced`` lifecycle event.

    Shape per the content-policy contract: ``policy``,
    ``exemplar_set_id``, and ``similarity`` (mirrors the event's
    top-level ``score`` for explicitness in dashboards that index on
    the metadata bag).
    """
    metadata: dict[str, Any] = {
        "policy": firing.name,
        "exemplar_set_id": firing.exemplar_set_id,
    }
    if firing.decision.confidence is not None:
        metadata["similarity"] = firing.decision.confidence
    return metadata


def build_aggregate_refusal_envelope(
    firings: Sequence[ContentPolicyFiring],
    *,
    human_message: str = "Request rejected by a content policy.",
) -> RefusalEnvelope:
    """Build the aggregate refusal envelope for one or more matched policies.

    Primary code = first firing's ``refusal_code`` (or ``POLICY_BLOCK``
    when None). ``metadata.firing_policies`` lists every firing with
    name, code, and confidence so operators can triage which of
    multiple content policies a request violated.
    """
    if not firings:
        raise ValueError("build_aggregate_refusal_envelope: firings is empty")
    primary = firings[0]
    primary_code = primary.decision.refusal_code or RefusalCode.POLICY_BLOCK
    firing_payload: list[dict[str, Any]] = []
    for f in firings:
        entry: dict[str, Any] = {
            "name": f.name,
            "refusal_code": (
                f.decision.refusal_code.value
                if f.decision.refusal_code is not None
                else RefusalCode.POLICY_BLOCK.value
            ),
        }
        if f.decision.confidence is not None:
            entry["confidence"] = f.decision.confidence
        firing_payload.append(entry)
    metadata: dict[str, Any] = {
        "firing_policies": firing_payload,
        "primary_policy": primary.name,
    }
    return RefusalEnvelope(
        code=primary_code.value,
        trigger="content_policy",
        policy=primary.name,
        human_message=human_message,
        metadata=metadata,
    )


__all__ = [
    "ContentPolicyFiring",
    "evaluate_content_policies",
    "build_finding_metadata",
    "build_aggregate_refusal_envelope",
    "exemplar_set_id",
]
