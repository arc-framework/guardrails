"""arc-guard-service — transport-neutral deployment surface for arc-guardrails.

Two entrypoints:

- ``run_guard(input)`` — synchronous adapter for ``GuardPipeline.pre_process``.
  Works without any optional extras installed.
- ``python -m arc_guard_service`` — HTTP service CLI; requires the ``[fastapi]``
  extra. The CLI exits with a friendly ImportError when the extra is missing.

The HTTP transport (``arc_guard_service.transport``) lives behind a lazy
import; importing this package without the extra succeeds.
"""

from __future__ import annotations

from arc_guard_service.runner import run_guard
from arc_guard_service.settings import ServiceSettings

__version__ = "0.6.0"

__all__ = [
    "__version__",
    "run_guard",
    "ServiceSettings",
]
