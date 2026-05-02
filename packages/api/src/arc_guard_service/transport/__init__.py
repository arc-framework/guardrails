"""HTTP transport for arc-guard-service.

Lazy-imported behind the ``[fastapi]`` extra. Importing this sub-package
without the extra succeeds; calling ``create_app(...)`` is the boundary
that imports ``fastapi`` and raises ``ImportError`` with a friendly
install hint when the extra is missing.
"""

from __future__ import annotations

from arc_guard_service.transport.http import create_app

__all__ = ["create_app"]
