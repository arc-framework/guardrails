"""Config validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from arc_guard_core.config import GuardConfig
from arc_guard_core.exceptions import ConfigCrossFieldError


def test_unknown_field_rejected() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        GuardConfig.model_validate({"enabled": True, "totally_unknown": 42})
    assert "totally_unknown" in str(excinfo.value)


def test_wrong_type_rejected() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        GuardConfig.model_validate({"enabled": "not-a-bool"})
    assert "enabled" in str(excinfo.value).lower()


def _expect_config_cross_field_error(callable_, *args, **kwargs) -> ConfigCrossFieldError:
    """Pydantic wraps validator-raised exceptions in ValidationError; the
    original ConfigCrossFieldError is attached as the cause. Surface either
    form so direct construction and ``model_validate`` both pass.
    """
    with pytest.raises((ConfigCrossFieldError, PydanticValidationError)) as excinfo:
        callable_(*args, **kwargs)
    if isinstance(excinfo.value, ConfigCrossFieldError):
        return excinfo.value
    # Pydantic ValidationError wraps the original.
    cause = getattr(excinfo.value, "__cause__", None)
    if isinstance(cause, ConfigCrossFieldError):
        return cause
    # Fall back: extract from .errors() if pydantic stored the original
    for err in excinfo.value.errors():
        ctx = err.get("ctx") or {}
        nested = ctx.get("error")
        if isinstance(nested, ConfigCrossFieldError):
            return nested
    raise AssertionError(
        f"expected ConfigCrossFieldError (direct or wrapped), got {excinfo.value!r}"
    )


def test_inspector_order_duplicate_rejected() -> None:
    err = _expect_config_cross_field_error(
        GuardConfig.model_validate, {"inspector_order": ["a", "b", "a"]}
    )
    assert err.code == "config.cross_field_violation"
    assert "inspector_order" in err.details["field"]


def test_inspector_order_empty_string_rejected() -> None:
    err = _expect_config_cross_field_error(
        GuardConfig.model_validate, {"inspector_order": ["", "x"]}
    )
    assert err.code == "config.cross_field_violation"


def test_policy_hints_default_empty_string_rejected() -> None:
    err = _expect_config_cross_field_error(
        GuardConfig.model_validate, {"policy_hints_default": [""]}
    )
    assert "policy_hints_default" in err.details["field"]


def test_disabled_skips_cross_field_checks() -> None:
    # When disabled, cross-field validation should be permissive — the pipeline
    # never reads those fields anyway.
    cfg = GuardConfig.model_validate(
        {"enabled": False, "inspector_order": ["a", "a"]}
    )
    assert cfg.enabled is False
