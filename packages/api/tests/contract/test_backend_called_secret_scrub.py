"""Contract: model-config helpers keep credentials off the lifecycle wire.

Two layers of safety verified here:

1. ``_build_model_config_snapshot`` uses a whitelist (only the four
   permitted keys are ever copied), so credentials in other payload
   fields can never end up in the snapshot — even fields with
   credential-shaped names.
2. ``_scrub_forbidden_keys`` is a separate helper that drops any
   dict entry whose key contains a forbidden substring. Used for
   ad-hoc dicts where the keys are not known statically.
"""

from __future__ import annotations

from arc_guard_service.transport.openai import (
    _build_model_config_snapshot,
    _scrub_forbidden_keys,
)


def test_snapshot_excludes_api_key_field() -> None:
    """A payload with an api_key field never leaks into the snapshot."""
    snap = _build_model_config_snapshot(
        provider="openai",
        payload={"model": "gpt-4o", "api_key": "sk-leak-DO-NOT-LOG"},
    )
    assert snap is not None
    assert "api_key" not in snap


def test_snapshot_excludes_arbitrary_extra_keys() -> None:
    """Anything beyond the four permitted keys is dropped."""
    snap = _build_model_config_snapshot(
        provider="openai",
        payload={
            "model": "gpt-4o",
            "secret": "x",
            "auth_header": "y",
            "rogue_field": "z",
        },
    )
    assert snap == {"provider": "openai", "model": "gpt-4o"}


def test_snapshot_includes_max_tokens() -> None:
    """The whitelist explicitly permits max_tokens — must not be stripped
    by overzealous credential filtering."""
    snap = _build_model_config_snapshot(
        provider="openai",
        payload={"model": "gpt-4o", "max_tokens": 100},
    )
    assert snap is not None
    assert snap["max_tokens"] == 100


def test_snapshot_temperature_must_be_numeric() -> None:
    """A non-numeric temperature is silently dropped (not coerced)."""
    snap = _build_model_config_snapshot(
        provider="openai",
        payload={"model": "gpt-4o", "temperature": "high"},
    )
    assert snap is not None
    assert "temperature" not in snap


def test_scrubber_strips_credential_substrings() -> None:
    """Standalone scrubber: drops keys matching the forbidden substrings."""
    out = _scrub_forbidden_keys(
        {
            "safe_field": 1,
            "api_key": "leak",
            "auth_header": "x",
            "user_password": "p",
            "session_token": "t",
            "client_secret": "s",
            "normal_field": 2,
        }
    )
    assert out == {"safe_field": 1, "normal_field": 2}


def test_scrubber_is_case_insensitive() -> None:
    out = _scrub_forbidden_keys({"API_KEY": "leak", "Auth_Header": "x", "normal": 1})
    assert out == {"normal": 1}


def test_scrubber_does_not_mutate_input() -> None:
    src = {"api_key": "leak", "safe": 1}
    _ = _scrub_forbidden_keys(src)
    assert "api_key" in src  # original unchanged
