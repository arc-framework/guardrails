"""tools/check_import_graph.py — boundary enforcement.

Wraps ``import-linter`` against ``packages/.importlinter`` and additionally
asserts that loading ``arc_guard_core`` at runtime does not pull any
forbidden provider module into ``sys.modules``.

Exit codes:
    0 — all rules pass
    1 — one or more rules violated, or a forbidden module loaded at runtime
    2 — invocation error (missing files, etc.)

Usage:
    python tools/check_import_graph.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "packages" / ".importlinter"

FORBIDDEN_AT_RUNTIME = {
    "presidio_analyzer",
    "presidio_anonymizer",
    "nats",
    "UnleashClient",
    "httpx",
    "opentelemetry",
    "torch",
    "transformers",
}


def run_import_linter() -> int:
    if not CONFIG.exists():
        print(f"ERROR: import-linter config not found at {CONFIG}", file=sys.stderr)
        return 2
    proc = subprocess.run(
        ["lint-imports", "--config", str(CONFIG)],
        cwd=ROOT / "packages",
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def check_runtime_isolation() -> int:
    code = (
        "import sys\n"
        "import arc_guard_core  # noqa: F401\n"
        "forbidden = " + repr(sorted(FORBIDDEN_AT_RUNTIME)) + "\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "if loaded:\n"
        "    print('runtime isolation violation: ' + ','.join(loaded))\n"
        "    raise SystemExit(1)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def main() -> int:
    rc1 = run_import_linter()
    rc2 = check_runtime_isolation()
    if rc1 != 0 or rc2 != 0:
        return 1
    print("import-graph: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
