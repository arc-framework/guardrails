#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[check] running package lint"
make -C "$ROOT_DIR" lint

echo "[check] running package type checks"
make -C "$ROOT_DIR" typecheck

echo "[check] running package test suites"
make -C "$ROOT_DIR" test

echo "[check] running architecture boundary checks"
make -C "$ROOT_DIR" boundary

echo "[check] running docs link check"
make -C "$ROOT_DIR" docs-links

echo "[check] verifying public surface manifest"
cd "$ROOT_DIR/packages"
uv run --package arc-guard python ../tools/check_public_surface.py