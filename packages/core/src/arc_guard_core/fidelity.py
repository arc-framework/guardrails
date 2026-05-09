"""Fidelity score type — the result a ``FidelityScorer`` produces.

The score is a frozen dataclass with two fields: a ``value`` in
``[0.0, 1.0]`` (or ``None`` for the sentinel) and a typed ``sentinel``
discriminator. Constructed via the two classmethod factories so callers
never accidentally combine a measured value with the not-measured marker.

The module-level ``NOT_MEASURED`` singleton is the canonical sentinel
returned by the null encoder/scorer pair when no concrete backend is
configured. Threshold-ladder code branches on
``score.sentinel == "measured"`` rather than ``score.value is not None``
because the typed marker reads more clearly at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

FidelitySentinel = Literal["measured", "not_measured"]


@dataclass(frozen=True)
class FidelityScore:
    """A fidelity score in ``[0.0, 1.0]`` or the ``not_measured`` sentinel.

    Validation rules:

    - ``sentinel == "measured"`` requires ``value`` in ``[0.0, 1.0]``.
    - ``sentinel == "not_measured"`` requires ``value is None``.

    Constructed via :meth:`measured` and :meth:`not_measured` rather than
    direct field assignment so the discriminator and value stay in sync.
    """

    value: float | None
    sentinel: FidelitySentinel

    def __post_init__(self) -> None:
        if self.sentinel == "measured":
            if self.value is None:
                raise ValueError("FidelityScore(sentinel='measured') requires a value")
            if not (0.0 <= self.value <= 1.0):
                raise ValueError(f"FidelityScore.value must be in [0.0, 1.0]; got {self.value}")
        else:
            if self.value is not None:
                raise ValueError("FidelityScore(sentinel='not_measured') must have value=None")

    @classmethod
    def measured(cls, value: float) -> FidelityScore:
        return cls(value=value, sentinel="measured")

    @classmethod
    def not_measured(cls) -> FidelityScore:
        return cls(value=None, sentinel="not_measured")


NOT_MEASURED: Final[FidelityScore] = FidelityScore(value=None, sentinel="not_measured")


__all__ = [
    "FidelitySentinel",
    "FidelityScore",
    "NOT_MEASURED",
]
