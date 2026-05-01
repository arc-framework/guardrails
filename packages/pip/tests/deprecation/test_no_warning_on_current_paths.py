"""T069 — current `arc_guard_core.*` paths fire no DeprecationWarning."""

from __future__ import annotations

import warnings


def test_canonical_imports_emit_no_warnings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes a test failure

        # Public surface re-exports — none of these should warn.
        from arc_guard_core import (  # noqa: F401
            ActionStrategy,
            EntityDefinition,
            EntityProvider,
            EntityRegistry,
            Finding,
            FlagProvider,
            Guard,
            GuardConfig,
            GuardContext,
            GuardInput,
            GuardPipeline,
            GuardResult,
            Inspector,
            Logger,
            MetricSink,
            Middleware,
            NullLogger,
            NullMetricSink,
            NullTracer,
            PolicyDecision,
            RefusalCode,
            RefusalEnvelope,
            Reporter,
            RiskLevel,
            Tracer,
            register_entity,
        )

        # Construct one of each typed model to exercise default field factories.
        ctx = GuardContext()
        gi = GuardInput(text="ok", context=ctx)
        result = GuardPipeline(config=GuardConfig()).pre_process_sync(gi)
        assert result.action == "pass"
