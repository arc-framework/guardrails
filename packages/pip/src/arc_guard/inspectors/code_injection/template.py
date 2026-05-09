"""TemplateInjectionInspector — flags template-engine sandbox-escape patterns
plus active HTML.

Two subtypes are surfaced:

- ``template.sandbox_escape`` — Jinja-style ``{{ ... }}`` or ``{% ... %}``
  sigils whose body contains one of the dunder traversal patterns known
  to escape a Jinja sandbox (``__class__``, ``__mro__``,
  ``__subclasses__``, ``__globals__``, ``__init__``, ``config.__class__``).
  Bare sigils without dunder traversal are NOT flagged so documentation
  about Jinja syntax is not affected.
- ``template.active_html`` — ``<script>`` / ``<iframe>`` / ``<svg>`` tags
  carrying active content; attributes matching ``^on[a-z]+=``; URLs
  starting with ``javascript:`` or ``data:text/html``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from arc_guard_core.exceptions import ConfigSchemaError
from arc_guard_core.observability import Logger, NullLogger
from arc_guard_core.types import Finding, GuardResult

from arc_guard.inspectors.code_injection._common import (
    build_code_injection_finding,
    closed_posture_inspect,
)

_DEFAULT_PHASES = frozenset({"post_process"})

_DUNDER_KEYWORDS = (
    "__class__",
    "__mro__",
    "__subclasses__",
    "__globals__",
    "__init__",
    "__bases__",
    "__builtins__",
)

_JINJA_SIGIL_RE = re.compile(
    r"\{\{.*?\}\}|\{%.*?%\}",
    re.DOTALL,
)

_ACTIVE_TAG_RE = re.compile(
    r"<\s*(?:script|iframe|svg)\b[^>]*>",
    re.IGNORECASE,
)

_EVENT_ATTR_RE = re.compile(
    r"\bon[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)

_DANGEROUS_URL_RE = re.compile(
    r"(?:javascript:[^\s\"'<>]+|data:text/html[^\s\"'<>]*)",
    re.IGNORECASE,
)


class TemplateInjectionInspector:
    """Inspector that flags template-engine sandbox-escape patterns and active HTML."""

    name: str = "TemplateInjectionInspector"

    def __init__(
        self,
        *,
        capture_raw_matches: bool = False,
        max_input_chars: int = 100_000,
        phases: Iterable[str] = _DEFAULT_PHASES,
        logger: Logger | None = None,
    ) -> None:
        if max_input_chars <= 0:
            raise ConfigSchemaError(
                "TemplateInjectionInspector: max_input_chars must be > 0",
                code="config.type_mismatch",
                details={"field": "max_input_chars"},
            )
        self._capture_raw_matches = bool(capture_raw_matches)
        self._max_input_chars = int(max_input_chars)
        self._phases = frozenset(phases)
        self._logger: Logger = logger or NullLogger()
        self._py_logger = logging.getLogger(__name__)

    @closed_posture_inspect
    async def inspect(self, result: GuardResult) -> GuardResult:
        if result.phase not in self._phases:
            return result

        text = result.text
        if len(text) > self._max_input_chars:
            self._emit_unparseable("size_limit", len(text))
            return result

        new_findings: list[Finding] = list(result.findings)
        new_findings.extend(self._detect_sandbox_escape(text))
        new_findings.extend(self._detect_active_html(text))

        if len(new_findings) == len(result.findings):
            return result
        return GuardResult(
            text=result.text,
            action=result.action,
            findings=tuple(new_findings),
            bypass_reason=result.bypass_reason,
            phase=result.phase,
        )

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_sandbox_escape(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for match in _JINJA_SIGIL_RE.finditer(text):
            body = match.group(0)
            if not any(keyword in body for keyword in _DUNDER_KEYWORDS):
                continue
            out.append(
                build_code_injection_finding(
                    inspector_name=self.name,
                    subtype="template.sandbox_escape",
                    span=(match.start(), match.end()),
                    raw_text=body,
                    capture_raw_matches=self._capture_raw_matches,
                )
            )
        return out

    def _detect_active_html(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for pattern in (_ACTIVE_TAG_RE, _EVENT_ATTR_RE, _DANGEROUS_URL_RE):
            for match in pattern.finditer(text):
                raw = match.group(0)
                out.append(
                    build_code_injection_finding(
                        inspector_name=self.name,
                        subtype="template.active_html",
                        span=(match.start(), match.end()),
                        raw_text=raw,
                        capture_raw_matches=self._capture_raw_matches,
                    )
                )
        return out

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def _emit_unparseable(self, reason: str, size: int) -> None:
        self._logger.event(
            "guard.code_injection.unparseable_input",
            level="warning",
            inspector=self.name,
            reason=reason,
            input_size=size,
        )
        self._py_logger.warning(
            "guard.code_injection.unparseable_input",
            extra={
                "inspector": self.name,
                "reason": reason,
                "input_size": size,
            },
        )


__all__ = ["TemplateInjectionInspector"]
