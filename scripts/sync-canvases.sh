#!/usr/bin/env bash
# Sync docs/canvases/ → apps/guardrail-flow/canvases/
#
# docs/canvases/ is the source of truth (Obsidian edits happen there).
# Run this after editing any canvas in docs/canvases/.
#
# Obsidian uses the .canvas extension; the app expects .canvas.json.
# Both are plain JSON with the same {nodes,edges} schema.
# old-flow.canvas is intentionally excluded — it is the historical
# pre-rewrite reference and the app does not ship it.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/docs/canvases"
DST="$REPO_ROOT/apps/guardrail-flow/canvases"

CANVASES=(new-flow request-flow request-dag-sample)

echo "Syncing canvases: $SRC → $DST"

for slug in "${CANVASES[@]}"; do
  src_file="$SRC/${slug}.canvas"
  dst_file="$DST/${slug}.canvas.json"

  if [[ ! -f "$src_file" ]]; then
    echo "  SKIP  $slug (source not found: $src_file)"
    continue
  fi

  if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$src_file" 2>/dev/null; then
    echo "  ERROR $slug — source file is not valid JSON, aborting"
    exit 1
  fi

  cp "$src_file" "$dst_file"
  echo "  OK    $slug"
done

echo "Done."
