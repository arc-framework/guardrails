#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/python/arc-guardrails"

required_files=(
  "$ROOT_DIR/.specify/config.yaml"
  "$ROOT_DIR/.specify/modes.yaml"
  "$ROOT_DIR/.specify/memory/constitution.md"
  "$ROOT_DIR/.specify/memory/patterns.md"
  "$ROOT_DIR/.specify/memory/libraries.md"
  "$ROOT_DIR/.specify/docs/architecture/event-context.md"
  "$ROOT_DIR/.specify/docs/architecture/enterprise-python-standard.md"
  "$ROOT_DIR/specs/index.md"
)

echo "[release-check] verifying required governance files"
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "missing required file: $file" >&2; exit 1; }
done

cd "$PACKAGE_DIR"

echo "[release-check] verifying package metadata"
uv run python - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text())
project = data.get("project", {})
required = ["name", "version", "requires-python"]
missing = [key for key in required if key not in project]
if missing:
    raise SystemExit(f"missing project fields: {', '.join(missing)}")
print(f"package={project['name']} version={project['version']}")
PY

echo "[release-check] running quality gate"
"$ROOT_DIR/scripts/check.sh"