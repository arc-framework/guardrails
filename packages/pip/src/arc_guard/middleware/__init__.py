"""arc_guard.middleware — pipeline middleware implementations.

The OTEL adapter lives at ``arc_guard.middleware.otel`` (gated by
``arc-guard[otel]``); the semantic backend at
``arc_guard.middleware.semantic`` (gated by ``arc-guard[semantic]``);
the canned ML jailbreak backend at
``arc_guard.middleware.jailbreak_ml`` (gated by
``arc-guard[jailbreak-ml]``). Top-level lazy-import factories ensure a
bare ``import arc_guard.middleware`` succeeds whether or not the
extras are installed; the import-error message is friendly when the
operator calls a factory without the matching extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arc_guard.middleware.jailbreak_ml import JailbreakMlBundle  # noqa: F401
    from arc_guard.middleware.otel import OtelObservability  # noqa: F401
    from arc_guard.middleware.semantic import SemanticBundle  # noqa: F401


def from_otel_sdk(*, instrumentation_name: str = "arc-guardrails") -> Any:
    """Build OTEL-backed observability adapters from the SDK's
    auto-configured providers.

    Returns an ``OtelObservability`` bundle exposing ``.tracer``,
    ``.logger``, and ``.metric_sink`` attributes that satisfy the
    foundation's observability Protocols.

    Raises:
        ImportError: when ``arc-guard[otel]`` is not installed. The
            message tells the operator how to fix it.
    """
    try:
        from arc_guard.middleware.otel import OtelObservability
    except ImportError as exc:
        raise ImportError(
            "from_otel_sdk() requires the [otel] extra. "
            "Install with: pip install arc-guard[otel]"
        ) from exc
    return OtelObservability.from_otel_sdk(instrumentation_name=instrumentation_name)


def from_sentence_transformers(
    *,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    injection_inspector: Any | None = None,
) -> Any:
    """Build the canned semantic backend (encoder + scorer + verifier).

    Returns a ``SemanticBundle`` whose ``.encoder``, ``.scorer``, and
    ``.verifier`` attributes plug into ``GuardPipeline`` directly.

    Raises:
        ImportError: when ``arc-guard[semantic]`` is not installed.
    """
    try:
        from arc_guard.middleware.semantic import SemanticBundle
    except ImportError as exc:
        raise ImportError(
            "from_sentence_transformers() requires the [semantic] extra. "
            "Install with: pip install arc-guard[semantic]"
        ) from exc
    return SemanticBundle.from_sentence_transformers(
        model_name=model_name,
        injection_inspector=injection_inspector,
    )


def from_huggingface_jailbreak(
    *,
    model_name: str = "protectai/deberta-v3-base-prompt-injection-v2",
    device: str | None = None,
) -> Any:
    """Build the canned ML jailbreak detector.

    Returns a ``JailbreakMlBundle`` whose ``.detector`` attribute plugs
    into ``GuardPipeline(jailbreak_detector=...)`` directly.

    Raises:
        ImportError: when ``arc-guard[jailbreak-ml]`` is not installed.
    """
    try:
        from arc_guard.middleware.jailbreak_ml import JailbreakMlBundle
    except ImportError as exc:
        raise ImportError(
            "from_huggingface_jailbreak() requires the [jailbreak-ml] extra. "
            "Install with: pip install arc-guard[jailbreak-ml]"
        ) from exc
    return JailbreakMlBundle.from_huggingface_jailbreak(
        model_name=model_name, device=device,
    )


__all__ = [
    "from_otel_sdk",
    "from_sentence_transformers",
    "from_huggingface_jailbreak",
]
