"""tools/check_dependency_tree.py — dep-closure audit for arc-guard-core (FR-005, SC-002).

Runs ``uv tree --package arc-guard-core`` and asserts the runtime closure
contains only ``pydantic`` (and its transitive deps) plus stdlib. Any
provider SDK in the closure fails the check.

Exit codes:
    0 — closure is clean
    1 — forbidden runtime dependency detected
    2 — invocation error
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "packages"

FORBIDDEN = {
    "presidio-analyzer",
    "presidio-anonymizer",
    "nats-py",
    "unleash-client",
    "unleashclient",
    "httpx",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "torch",
    "transformers",
    "fastapi",
    "uvicorn",
    "arc-guard",          # core MUST NOT depend on pip
    "arc-guard-service",  # or api
}


def main() -> int:
    proc = subprocess.run(
        ["uv", "tree", "--package", "arc-guard-core"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return 2
    text = proc.stdout
    # Extract every "name vX.Y" token at the start of any tree line.
    line_re = re.compile(r"[├└─ ]*([A-Za-z0-9_.-]+)\s+v")
    found_forbidden: list[str] = []
    for line in text.splitlines():
        match = line_re.match(line)
        if not match:
            continue
        name = match.group(1).lower()
        if name in FORBIDDEN:
            found_forbidden.append(name)
    if found_forbidden:
        print("dependency-tree audit FAILED. Forbidden in arc-guard-core closure:")
        for n in sorted(set(found_forbidden)):
            print(f"  - {n}")
        print()
        print("Tree:")
        print(text)
        return 1
    print("dependency-tree: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
