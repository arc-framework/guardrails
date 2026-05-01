"""Unit tests for the typed exception hierarchy."""

from __future__ import annotations

import pytest

from arc_guard_core import exceptions as exc

LEAF_CLASSES = [
    exc.ConfigSchemaError,
    exc.ConfigCrossFieldError,
    exc.ApiBoundaryValidationError,
    exc.PipelineContractValidationError,
    exc.AdapterBoundaryValidationError,
    exc.InspectorError,
    exc.StrategyError,
    exc.PolicyRouterError,
    exc.ReporterError,
    exc.FlagProviderError,
    exc.EntityProviderError,
    exc.RefusalEnvelopeError,
]


@pytest.mark.parametrize("klass", LEAF_CLASSES)
def test_leaf_has_failure_mode_marker(klass: type[exc.ArcGuardError]) -> None:
    assert hasattr(klass, "__failure_mode__")
    assert klass.__failure_mode__ in {"open", "closed", "closed-conservative"}


@pytest.mark.parametrize("klass", LEAF_CLASSES)
def test_leaf_has_valid_codes(klass: type[exc.ArcGuardError]) -> None:
    assert hasattr(klass, "__valid_codes__")
    assert isinstance(klass.__valid_codes__, frozenset)
    assert len(klass.__valid_codes__) >= 1


@pytest.mark.parametrize("klass", LEAF_CLASSES)
def test_init_validates_code(klass: type[exc.ArcGuardError]) -> None:
    valid = next(iter(klass.__valid_codes__))
    instance = klass("ok", code=valid, details={"field": "x"})
    assert instance.code == valid
    assert instance.details == {"field": "x"}

    with pytest.raises(ValueError):
        klass("nope", code="not.a.real.code")


def test_cause_attached() -> None:
    underlying = RuntimeError("boom")
    err = exc.InspectorError("wrap", code="inspector.unhandled", cause=underlying)
    assert err.__cause__ is underlying


def test_base_error_is_abstract_in_use() -> None:
    # ArcGuardError has no __valid_codes__; constructing it with any code is allowed.
    instance = exc.ArcGuardError("base", code="any")
    assert instance.code == "any"
