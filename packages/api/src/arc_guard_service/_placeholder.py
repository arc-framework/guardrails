"""Spec 007 handoff placeholder.

Spec 002 leaves ``arc-guard-service`` as a thin scaffold so:
- the workspace's layered import-graph rule has a real ``api`` package to
  exercise; and
- integrators can install the distribution to verify shape, even though no
  routes are wired yet.

Spec 007 will replace this module with the full app factory, route handlers,
DI wiring, request/response models, and integration documentation.

Until then, importing this module documents the handoff.
"""

from __future__ import annotations

HANDOFF_NOTE = (
    "arc-guard-service is a Spec 002 scaffold. Full deployment surface "
    "is owned by Spec 007."
)

__all__ = ["HANDOFF_NOTE"]
