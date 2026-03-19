#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/python/arc-guardrails"

cd "$PACKAGE_DIR"

echo "[verify-adapters] importing core package"
uv run python - <<'PY'
import arc_guard
print("core import ok")
PY

echo "[verify-adapters] verifying adapter modules can be imported in the current environment"
uv run python - <<'PY'
modules = [
    "arc_guard.adapters.nats_reporter",
    "arc_guard.adapters.unleash_provider",
    "arc_guard.reporters.webhook_reporter",
    "arc_guard.middleware.otel",
]

for module in modules:
    try:
        __import__(module)
        print(f"{module}: import ok")
    except Exception as exc:
        print(f"{module}: import check failed -> {exc}")
PY