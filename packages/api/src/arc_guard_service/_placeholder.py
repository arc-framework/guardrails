"""Future-deployment handoff placeholder.

``arc-guard-service`` is a thin scaffold so:
- the workspace's layered import-graph rule has a real ``api`` package to
  exercise; and
- integrators can install the distribution to verify shape, even though no
  routes are wired yet.

A future deployment-surface implementation will replace this module with
the full app factory, route handlers, DI wiring, request/response models,
and integration documentation.

Until then, importing this module documents the handoff.
"""

from __future__ import annotations

HANDOFF_NOTE = (
    "arc-guard-service is a thin scaffold. The full deployment surface lands in a future spec."
)

__all__ = ["HANDOFF_NOTE"]
