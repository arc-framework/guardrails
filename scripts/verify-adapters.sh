#!/usr/bin/env bash
#
# Verify that each optional adapter installs and imports cleanly.
#
# Runs from the repo root; uses the workspace's `uv` environment so
# the locally-developed packages are exercised, not whatever
# arc-guard build happens to be on the system.

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/packages/pip"

echo "[verify-adapters] importing core package"
uv run python - <<'PY'
import arc_guard
import arc_guard_core
print("arc_guard:", arc_guard.__version__)
print("arc_guard_core:", arc_guard_core.__version__)
PY

echo "[verify-adapters] bare arc_guard.middleware import (no extras)"
uv run python - <<'PY'
import arc_guard.middleware
assert callable(arc_guard.middleware.from_otel_sdk)
print("bare middleware import: ok")
PY

echo "[verify-adapters] [otel] extra: round-trip via in-memory exporter"
uv run python - <<'PY'
import sys

try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
except ImportError as exc:
    print(f"[otel] extra not installed: {exc}")
    print("install with: uv pip install 'arc-guard[otel]'")
    sys.exit(1)

from arc_guard.middleware.otel import OtelTracer

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = OtelTracer(provider.get_tracer("verify-adapters"))

with tracer.start_span("guard.stage.classify", attributes={"stage": "classify"}):
    pass

spans = exporter.get_finished_spans()
assert len(spans) == 1, f"expected 1 span, got {len(spans)}"
assert spans[0].name == "guard.stage.classify"
print(f"[otel] round-trip: ok ({len(spans)} span captured)")
PY

echo "[verify-adapters] all checks passed"
