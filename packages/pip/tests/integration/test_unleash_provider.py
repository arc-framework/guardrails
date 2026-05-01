"""Tests for UnleashFlagProvider.

UnleashClient is not installed in CI — we test the import guard,
then patch _UNLEASH_AVAILABLE to exercise all logic paths with a mock client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


def test_import_guard_raises_when_unleash_not_available() -> None:
    """ImportError raised at construction when UnleashClient is not installed."""
    import arc_guard.adapters.unleash_provider as mod

    with patch.object(mod, "_UNLEASH_AVAILABLE", False):
        try:
            mod.UnleashFlagProvider(client=MagicMock())
            raised = False
        except ImportError as exc:
            raised = True
            assert "arc-guard[unleash]" in str(exc)
    assert raised


def _make_provider() -> Any:
    import arc_guard.adapters.unleash_provider as mod

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        return mod.UnleashFlagProvider(client=MagicMock())


def test_is_enabled_delegates_to_unleash_client() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.is_enabled.return_value = True

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    result = provider.is_enabled("lite_mode", default=False)

    assert result is True
    mock_client.is_enabled.assert_called_once_with("arc.guard.lite_mode", default=False)


def test_is_enabled_returns_default_on_exception() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.is_enabled.side_effect = RuntimeError("network error")

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    result = provider.is_enabled("enabled", default=True)
    assert result is True  # falls back to default


def test_get_string_extracts_payload_value() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "payload": {"type": "string", "value": "block"},
    }

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    result = provider.get_string("action_strategy", default="redact")
    assert result == "block"


def test_get_string_returns_default_when_disabled() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.return_value = {"enabled": False}

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    result = provider.get_string("action_strategy", default="redact")
    assert result == "redact"


def test_get_string_returns_default_when_no_payload() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.return_value = {"enabled": True, "payload": None}

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    assert provider.get_string("x", default="fallback") == "fallback"


def test_get_string_returns_default_on_exception() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.side_effect = ConnectionError("timeout")

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    assert provider.get_string("x", default="safe") == "safe"


def test_get_list_splits_on_comma() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "payload": {"value": "PERSON, CREDIT_CARD, EMAIL_ADDRESS"},
    }

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    result = provider.get_list("pii_entities")
    assert result == ["PERSON", "CREDIT_CARD", "EMAIL_ADDRESS"]


def test_get_list_returns_default_when_empty() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.get_variant.return_value = {"enabled": False}

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    assert provider.get_list("x", default=["a", "b"]) == ["a", "b"]


def test_toggle_namespaces_flag() -> None:
    import arc_guard.adapters.unleash_provider as mod

    mock_client = MagicMock()
    mock_client.is_enabled.return_value = False

    with patch.object(mod, "_UNLEASH_AVAILABLE", True):
        provider = mod.UnleashFlagProvider(client=mock_client)

    provider.is_enabled("my_flag")
    mock_client.is_enabled.assert_called_once_with("arc.guard.my_flag", default=False)
