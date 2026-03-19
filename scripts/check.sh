#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/python/arc-guardrails"

cd "$PACKAGE_DIR"

echo "[check] running ruff format check"
uv run ruff format --check .

echo "[check] running ruff lint"
uv run ruff check src tests

echo "[check] running mypy"
uv run mypy src

echo "[check] running pytest with coverage"
uv run pytest --cov=src/arc_guard --cov-report=term-missing