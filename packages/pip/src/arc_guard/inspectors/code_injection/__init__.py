"""Code-injection inspectors — SQL, shell, and template engines.

These inspectors target the data-flowing-into-tools threat: an LLM
emitting executable artifacts that a downstream tool will run. They are
opt-in (the operator must include them in
``GuardPipeline(inspectors=...)``) and default to running on
``post_process`` only.

By default, findings carry a fingerprint of the matched substring (hash,
length, char-class summary) but NOT the literal payload. Operators who
need the literal text in lifecycle events pass
``capture_raw_matches=True`` per inspector instance.
"""

from __future__ import annotations

from arc_guard.inspectors.code_injection._common import (
    build_code_injection_finding,
)
from arc_guard.inspectors.code_injection._fingerprint import compute_fingerprint
from arc_guard.inspectors.code_injection.shell import ShellInjectionInspector
from arc_guard.inspectors.code_injection.sql import SqlInjectionInspector
from arc_guard.inspectors.code_injection.template import (
    TemplateInjectionInspector,
)

__all__ = [
    "SqlInjectionInspector",
    "ShellInjectionInspector",
    "TemplateInjectionInspector",
    "compute_fingerprint",
    "build_code_injection_finding",
]
