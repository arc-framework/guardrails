"""InjectionInspector — regex-based prompt injection detector."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from arc_guard.types import Finding, GuardResult, RiskLevel

_LOG = logging.getLogger(__name__)

_BUILTIN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"disregard", re.IGNORECASE),
    re.compile(r"forget\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"bypass", re.IGNORECASE),
    re.compile(r"act\s+as", re.IGNORECASE),
    re.compile(r"roleplay\s+as", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+are", re.IGNORECASE),
]


@dataclass
class InjectionInspector:
    """Regex-based prompt injection detector.

    Matches a set of known injection/jailbreak patterns against the input text.
    Only runs on pre-process (input) phase — post-process results are returned
    unchanged.

    Args:
        extra_patterns: Additional compiled regex patterns to check beyond the
            built-in set.
    """

    extra_patterns: list[re.Pattern[str]] = field(default_factory=list)

    def __init__(self, extra_patterns: list[re.Pattern[str]] | None = None) -> None:
        self.extra_patterns = extra_patterns or []
        self._all_patterns = _BUILTIN_PATTERNS + self.extra_patterns

    async def inspect(self, result: GuardResult) -> GuardResult:
        """Inspect for prompt injection patterns.

        Returns the result unchanged when phase is post_process.
        Never raises — all exceptions are caught internally.
        """
        if result.phase == "post_process":
            return result

        try:
            new_findings = list(result.findings)
            text = result.text

            for pattern in self._all_patterns:
                for match in pattern.finditer(text):
                    new_findings.append(
                        Finding(
                            entity_type="INJECTION",
                            start=match.start(),
                            end=match.end(),
                            risk_level=RiskLevel.CRITICAL,
                            inspector="injection",
                        )
                    )

            if not new_findings or len(new_findings) == len(result.findings):
                return result

            return GuardResult(
                text=result.text,
                action=result.action,
                findings=tuple(new_findings),
                bypass_reason=result.bypass_reason,
                phase=result.phase,
            )
        except Exception:
            _LOG.exception("InjectionInspector encountered an unexpected error")
            return result
