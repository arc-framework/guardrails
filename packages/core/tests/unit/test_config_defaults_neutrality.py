"""Configuration defaults must be product-neutral."""

from __future__ import annotations

import re

from arc_guard_core.config import GuardConfig

FORBIDDEN_TOKENS = [
    # provider names
    "nats",
    "unleash",
    "presidio",
    "arc.ai",
    "arc-ai",
    "opentelemetry",
    "transformers",
    "torch",
    # platform-specific filesystem hints
    "/var/",
    "/etc/",
    "/usr/local/",
    "C:\\",
    # logger / subject conventions that imply a specific platform
    "arc.ai.guard",
    "arc-guard.events",
]

FORBIDDEN_RE = re.compile("|".join(re.escape(t) for t in FORBIDDEN_TOKENS), re.IGNORECASE)


def _walk(value: object) -> list[str]:
    """Yield every stringy thing in *value* recursively."""
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_walk(v))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            out.extend(_walk(item))
    return out


def test_guard_config_defaults_are_product_neutral() -> None:
    """Default GuardConfig must contain no provider names, NATS subjects,
    platform-specific paths, or logger names that imply a specific platform.
    """
    cfg = GuardConfig()
    # model_dump returns the structural shape; observability hooks are
    # arbitrary types, so we walk the public fields explicitly.
    candidates = [
        repr(cfg.enabled),
        repr(cfg.lite_mode),
        *(s for s in cfg.inspector_order),
        *(s for s in cfg.policy_hints_default),
        # ConfigField defaults shouldn't contain provider names
    ]
    for candidate in candidates:
        match = FORBIDDEN_RE.search(candidate)
        assert match is None, (
            f"Default config value {candidate!r} contains forbidden token "
            f"{match.group()!r}"
        )


def test_inspector_order_default_is_empty() -> None:
    """`core` registers no inspectors by default; the implementation package wires them."""
    cfg = GuardConfig()
    assert cfg.inspector_order == ()


def test_policy_hints_default_is_empty() -> None:
    cfg = GuardConfig()
    assert cfg.policy_hints_default == frozenset()


def test_observability_defaults_are_null_implementations() -> None:
    """Defaults must be no-ops, not provider-coupled implementations."""
    from arc_guard_core.observability import NullLogger, NullMetricSink, NullTracer

    cfg = GuardConfig()
    assert isinstance(cfg.tracer, NullTracer)
    assert isinstance(cfg.logger, NullLogger)
    assert isinstance(cfg.metrics, NullMetricSink)
