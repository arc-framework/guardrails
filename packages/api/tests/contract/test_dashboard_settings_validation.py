"""Contract: ``ServiceSettings.dashboard_origins`` validator rejects every
invalid origin shape documented in
``specs/012-dashboard-backend-data-plane/contracts/cors-configuration.md``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arc_guard_service.settings import ServiceSettings


def test_default_is_empty_list() -> None:
    """Cross-origin requests are rejected by default."""
    settings = ServiceSettings()
    assert settings.dashboard_origins == []


def test_valid_http_origin_accepted() -> None:
    settings = ServiceSettings(dashboard_origins=["http://127.0.0.1:5173"])
    assert settings.dashboard_origins == ["http://127.0.0.1:5173"]


def test_valid_https_origin_accepted() -> None:
    settings = ServiceSettings(dashboard_origins=["https://dashboard.example.com"])
    assert settings.dashboard_origins == ["https://dashboard.example.com"]


def test_multiple_origins_accepted() -> None:
    settings = ServiceSettings(
        dashboard_origins=[
            "http://127.0.0.1:5173",
            "https://dashboard.example.com",
        ]
    )
    assert len(settings.dashboard_origins) == 2


def test_comma_separated_string_coerced_to_list() -> None:
    """Env-var style — pydantic-settings receives a single string from the
    env; the validator splits on commas."""
    settings = ServiceSettings.model_validate(
        {
            "dashboard_origins": "http://127.0.0.1:5173,https://dashboard.example.com",
        }
    )
    assert settings.dashboard_origins == [
        "http://127.0.0.1:5173",
        "https://dashboard.example.com",
    ]


def test_wildcard_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard not allowed"):
        ServiceSettings(dashboard_origins=["http://*.example.com"])


def test_bare_wildcard_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard not allowed"):
        ServiceSettings(dashboard_origins=["*"])


def test_non_http_scheme_rejected() -> None:
    with pytest.raises(ValidationError, match="scheme must be http or https"):
        ServiceSettings(dashboard_origins=["ws://dashboard.example.com"])


def test_file_scheme_rejected() -> None:
    with pytest.raises(ValidationError, match="scheme must be http or https"):
        ServiceSettings(dashboard_origins=["file:///dashboard.html"])


def test_trailing_slash_rejected() -> None:
    with pytest.raises(ValidationError, match="trailing slash not allowed"):
        ServiceSettings(dashboard_origins=["https://dashboard.example.com/"])


def test_path_component_rejected() -> None:
    with pytest.raises(ValidationError, match="path component not allowed"):
        ServiceSettings(dashboard_origins=["https://dashboard.example.com/admin"])


def test_query_component_rejected() -> None:
    with pytest.raises(ValidationError, match="query component not allowed"):
        ServiceSettings(dashboard_origins=["https://dashboard.example.com?foo=bar"])


def test_fragment_component_rejected() -> None:
    with pytest.raises(ValidationError, match="fragment component not allowed"):
        ServiceSettings(dashboard_origins=["https://dashboard.example.com#section"])


def test_missing_host_rejected() -> None:
    """`http:` (no `//`, no trailing slash) parses to an empty netloc."""
    with pytest.raises(ValidationError, match="missing host component"):
        ServiceSettings(dashboard_origins=["http:"])


def test_dashboard_page_size_caps_default() -> None:
    settings = ServiceSettings()
    assert settings.dashboard_max_request_page_size == 200
    assert settings.dashboard_max_debug_page_size == 200


def test_dashboard_queue_capacity_defaults() -> None:
    settings = ServiceSettings()
    assert settings.dashboard_decision_record_queue_capacity == 1000
    assert settings.dashboard_debug_entry_queue_capacity == 5000


def test_dashboard_page_size_lower_bound() -> None:
    with pytest.raises(ValidationError):
        ServiceSettings(dashboard_max_request_page_size=0)


def test_dashboard_page_size_upper_bound() -> None:
    with pytest.raises(ValidationError):
        ServiceSettings(dashboard_max_request_page_size=10_000)
