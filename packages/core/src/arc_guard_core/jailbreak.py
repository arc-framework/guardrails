"""Jailbreak signal types — emitted by ``JailbreakDetector`` implementations.

The signal carries a documented ``category`` (one of five canonical
values), a ``confidence`` in ``[0.0, 1.0]``, a placeholder
``evidence_reference`` (NEVER raw text — runtime-validated against the
``[A-Z][A-Z0-9_]*`` pattern), and the ``detector_id`` that produced it.

Detectors emit zero or more signals per input. The pipeline converts
each signal to a ``Finding`` so the existing policy router's
aggregation rules apply unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

JailbreakCategory = Literal[
    "role_play",
    "hypothetical",
    "policy_erosion",
    "indirect_injection",
    "direct_override",
]

_EVIDENCE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(r"[A-Z][A-Z0-9_]*")


@dataclass(frozen=True)
class JailbreakSignal:
    """One detected jailbreak signal.

    Validation rules:

    - ``confidence`` in ``[0.0, 1.0]``.
    - ``evidence_reference`` matches ``[A-Z][A-Z0-9_]*`` so detectors
      cannot accidentally smuggle raw user text into the audit record.
    - ``detector_id`` is non-empty.

    The dataclass is frozen so signals are safe to share across
    concurrent runs.
    """

    category: JailbreakCategory
    confidence: float
    evidence_reference: str
    detector_id: str

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"JailbreakSignal.confidence must be in [0.0, 1.0]; "
                f"got {self.confidence}"
            )
        if not self.evidence_reference:
            raise ValueError("JailbreakSignal.evidence_reference must be non-empty")
        if not _EVIDENCE_REFERENCE_PATTERN.fullmatch(self.evidence_reference):
            raise ValueError(
                f"JailbreakSignal.evidence_reference must match "
                f"[A-Z][A-Z0-9_]*; got {self.evidence_reference!r}"
            )
        if not self.detector_id:
            raise ValueError("JailbreakSignal.detector_id must be non-empty")


__all__ = ["JailbreakCategory", "JailbreakSignal"]
