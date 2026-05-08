"""arc_guard.content_policies — ContentPolicy implementations + registry.

Concrete bundled policies (``SemanticContentPolicy``) plug in once
implemented; this module only re-exports the registry surface.
"""

from __future__ import annotations

from arc_guard.content_policies.registry import (
    content_policy,
    freeze_content_policies,
    get_content_policy,
    is_content_policies_frozen,
    is_registered,
    list_registered,
    register_content_policy,
)

__all__ = [
    "register_content_policy",
    "get_content_policy",
    "is_registered",
    "list_registered",
    "freeze_content_policies",
    "is_content_policies_frozen",
    "content_policy",
]
