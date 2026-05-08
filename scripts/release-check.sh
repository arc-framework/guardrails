#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIRS=(
  "$ROOT_DIR/packages/core"
  "$ROOT_DIR/packages/pip"
  "$ROOT_DIR/packages/api"
)

echo "[release-check] verifying repository release assets"
if ! compgen -G "$ROOT_DIR/LICENSE*" >/dev/null; then
  echo "missing required release asset: LICENSE*" >&2
  exit 1
fi

echo "[release-check] verifying package metadata"
for package_dir in "${PACKAGE_DIRS[@]}"; do
  uv run python - "$package_dir" <<'PY'
from pathlib import Path
import sys
import tomllib

package_dir = Path(sys.argv[1])
data = tomllib.loads((package_dir / "pyproject.toml").read_text())
project = data.get("project", {})
required = [
    "name",
    "version",
    "description",
    "readme",
    "requires-python",
    "authors",
    "license",
]
missing = [key for key in required if key not in project]
if missing:
    raise SystemExit(f"{package_dir.name}: missing project fields: {', '.join(missing)}")
print(f"{package_dir.name}: package={project['name']} version={project['version']}")
PY
done

echo "[release-check] building distributions"
for package_dir in "${PACKAGE_DIRS[@]}"; do
  (
    cd "$package_dir"
    uv build
  )
done

echo "[release-check] running quality gate"
"$ROOT_DIR/scripts/check.sh"