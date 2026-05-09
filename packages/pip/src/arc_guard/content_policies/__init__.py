"""arc_guard.content_policies — ContentPolicy implementations + registry.

Exposes the registry surface (``register_content_policy`` and friends),
the bundled ``SemanticContentPolicy``, and the aggregate-evaluation
helper used by the pipeline integration point.
"""

from __future__ import annotations

from arc_guard.content_policies.aggregate import (
    ContentPolicyFiring,
    build_aggregate_refusal_envelope,
    build_finding_metadata,
    evaluate_content_policies,
    exemplar_set_id,
)
from arc_guard.content_policies.registry import (
    content_policy,
    freeze_content_policies,
    get_content_policy,
    is_content_policies_frozen,
    is_registered,
    list_registered,
    register_content_policy,
)
from arc_guard.content_policies.semantic import (
    GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT,
    SemanticContentPolicy,
)

__all__ = [
    "register_content_policy",
    "get_content_policy",
    "is_registered",
    "list_registered",
    "freeze_content_policies",
    "is_content_policies_frozen",
    "content_policy",
    "SemanticContentPolicy",
    "GUARD_CONTENT_POLICY_SEMANTIC_EXTRA_MISSING_EVENT",
    "ContentPolicyFiring",
    "evaluate_content_policies",
    "build_finding_metadata",
    "build_aggregate_refusal_envelope",
    "exemplar_set_id",
]
