#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SPECIFY_DIR="$ROOT_DIR/.specify"

required_files=(
  "$SPECIFY_DIR/config.yaml"
  "$SPECIFY_DIR/modes.yaml"
  "$SPECIFY_DIR/memory/constitution.md"
  "$SPECIFY_DIR/memory/patterns.md"
  "$SPECIFY_DIR/docs/architecture/event-context.md"
)

echo "[speckit-context] verifying project context assets"
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "missing required file: $file" >&2; exit 1; }
done

echo "[speckit-context] invoking SpecKit agent context updater"
exec "$SPECIFY_DIR/scripts/bash/update-agent-context.sh" "$@"