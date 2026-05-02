#!/usr/bin/env bash
#
# Verify that each optional adapter installs and imports cleanly.
#
# Runs from the repo root; uses the workspace's `uv` environment so
# the locally-developed packages are exercised, not whatever
# arc-guard build happens to be on the system.
#
# Each row is independent: a missing extra prints a "skipped" message
# rather than aborting the whole script. The exit code is non-zero
# only when an *installed* row's smoke check fails.

set -uo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

FAILED_ROWS=()
SKIPPED_ROWS=()

run_row() {
    local label="$1"
    local pkg_dir="$2"
    local script="$3"
    local skip_marker="$4"

    cd "$pkg_dir"
    if ! output="$(uv run python -c "$script" 2>&1)"; then
        if [[ "$output" == *"$skip_marker"* ]]; then
            echo "[verify-adapters] $label: SKIPPED (extra not installed)"
            SKIPPED_ROWS+=("$label")
        else
            echo "[verify-adapters] $label: FAILED"
            echo "$output"
            FAILED_ROWS+=("$label")
        fi
    else
        echo "[verify-adapters] $label: $output"
    fi
}

# Base import — no extras. MUST succeed.
echo "[verify-adapters] importing core package"
cd "$ROOT_DIR/packages/pip"
uv run python -c "
import arc_guard
import arc_guard_core
print(f'arc_guard: {arc_guard.__version__}')
print(f'arc_guard_core: {arc_guard_core.__version__}')
"

echo "[verify-adapters] bare arc_guard.middleware import (no extras)"
uv run python -c "
import arc_guard.middleware
assert callable(arc_guard.middleware.from_otel_sdk)
print('bare middleware import: ok')
"

# [otel] row — skips when extra missing.
run_row "[otel] round-trip via in-memory exporter" "$ROOT_DIR/packages/pip" "
import sys
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
except ImportError:
    sys.exit('__SKIP__: [otel] extra not installed')

from arc_guard.middleware.otel import OtelTracer

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = OtelTracer(provider.get_tracer('verify-adapters'))

with tracer.start_span('guard.stage.classify', attributes={'stage': 'classify'}):
    pass

spans = exporter.get_finished_spans()
assert len(spans) == 1, f'expected 1 span, got {len(spans)}'
assert spans[0].name == 'guard.stage.classify'
print(f'[otel] round-trip: ok ({len(spans)} span captured)')
" "__SKIP__"

# [semantic] row — skips when extra missing.
run_row "[semantic] encoder import smoke" "$ROOT_DIR/packages/pip" "
import sys
try:
    import sentence_transformers  # noqa: F401
except ImportError:
    sys.exit('__SKIP__: [semantic] extra not installed')

from arc_guard.middleware.semantic import SemanticBundle  # noqa: F401
print('[semantic] import: ok')
" "__SKIP__"

# [jailbreak-ml] row — skips when extra missing.
run_row "[jailbreak-ml] detector import smoke" "$ROOT_DIR/packages/pip" "
import sys
try:
    import transformers  # noqa: F401
    import torch  # noqa: F401
except ImportError:
    sys.exit('__SKIP__: [jailbreak-ml] extra not installed')

from arc_guard.middleware.jailbreak_ml import JailbreakMlBundle  # noqa: F401
print('[jailbreak-ml] import: ok')
" "__SKIP__"

# [fastapi] row — skips when extra missing.
run_row "[fastapi] api package boots an HTTP app" "$ROOT_DIR/packages/api" "
import sys
try:
    import fastapi  # noqa: F401
    import uvicorn  # noqa: F401
except ImportError:
    sys.exit('__SKIP__: [fastapi] extra not installed')

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

app = create_app(ServiceSettings())
routes = [r.path for r in app.routes if hasattr(r, 'path')]
assert '/v1/guard' in routes, f'expected /v1/guard route, got {routes}'
print(f'[fastapi] boot: ok ({len(routes)} route(s) mounted)')
" "__SKIP__"

echo
echo "[verify-adapters] summary:"
echo "  installed + ok: $(( 4 - ${#FAILED_ROWS[@]} - ${#SKIPPED_ROWS[@]} )) row(s)"
echo "  skipped (extra not installed): ${#SKIPPED_ROWS[@]} row(s)"
echo "  failed: ${#FAILED_ROWS[@]} row(s)"

if [[ ${#FAILED_ROWS[@]} -gt 0 ]]; then
    echo
    echo "[verify-adapters] FAILED rows:"
    for row in "${FAILED_ROWS[@]}"; do
        echo "  - $row"
    done
    exit 1
fi

echo "[verify-adapters] all installed checks passed"
