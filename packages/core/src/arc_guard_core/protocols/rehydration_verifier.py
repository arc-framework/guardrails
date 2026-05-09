"""RehydrationVerifier Protocol — gates placeholder reinsertion safety.

Implementations decide whether to rehydrate placeholders into a model's
answer. The verdict is one of three discriminator literals — ``accept``
(rehydrate everything), ``reject`` (keep placeholders, record reason),
or ``partial`` (rehydrate only the per-placeholder accepts). The
pipeline never blindly substitutes; it always consults the verifier.

Failure mode: implementations MUST NOT raise outward. Internal failures
are wrapped in ``RehydrationVerifierError`` whose foundation
``__failure_mode__`` is ``closed`` — when in doubt about whether
reinsertion is safe, the pipeline keeps the placeholders and records
the rejection reason on the decision record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

RehydrationDecision = Literal["accept", "reject", "partial"]


@dataclass(frozen=True)
class RehydrationVerdict:
    """Verifier output: discriminator + reason + per-placeholder breakdown.

    - ``decision == "accept"`` — rehydrate every placeholder; ``per_placeholder`` empty.
    - ``decision == "reject"`` — keep all placeholders; ``per_placeholder`` empty;
      ``reason`` identifies the failed check (``"invented_placeholder"``,
      ``"structural_shift"``, ``"safety_regression"``, ``"rehydration_verifier.verifier_failed"``).
    - ``decision == "partial"`` — rehydrate only the placeholders mapped to True
      in ``per_placeholder``; map MUST be non-empty.
    """

    decision: RehydrationDecision
    reason: str
    per_placeholder: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision == "partial" and not self.per_placeholder:
            raise ValueError(
                "RehydrationVerdict(decision='partial') requires non-empty per_placeholder"
            )
        if self.decision != "partial" and self.per_placeholder:
            raise ValueError(
                "RehydrationVerdict.per_placeholder must be empty unless decision='partial'"
            )


@runtime_checkable
class RehydrationVerifier(Protocol):
    """Decide whether to rehydrate placeholders into a model answer.

    Concurrency: thread-safe.
    Failure mode: implementations MUST NOT raise outward; internal
    failures bubble via ``RehydrationVerifierError`` (foundation
    ``__failure_mode__='closed'``) so the pipeline keeps placeholders
    and records the rejection reason on the decision record.
    """

    def verify(
        self,
        *,
        sanitized_prompt: str,
        rehydration_candidate: str,
        entity_map: Mapping[str, str],
    ) -> RehydrationVerdict:
        """Return a verdict for the candidate against the prompt + entity map."""


__all__ = [
    "RehydrationDecision",
    "RehydrationVerdict",
    "RehydrationVerifier",
]
