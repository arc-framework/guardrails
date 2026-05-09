"""Allow ``python -m arc_guard_service`` to invoke the CLI."""

from __future__ import annotations

from arc_guard_service.cli import main

raise SystemExit(main())
