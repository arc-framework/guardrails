"""tools/check_adopt_vs_build.py — runtime-dep audit for arc-guard-core.

Diffs the runtime dependency list in ``packages/core/pyproject.toml`` against
a baseline (``main`` by default) and requires every newly added entry to be
referenced from an adopt-vs-build record in either:

- ``.specify/memory/libraries.university`` (single-line adoption note), or
- ``specs/002-rewrite-foundation/decisions/<id>.university`` (full ADR with front-matter
  ``dependency: <name>``).

Dev-only dependencies under ``[dependency-groups.dev]`` or ``[tool.uv]`` are
exempt by policy.

Exit codes:
    0 — clean (no new runtime deps, or each new dep has a referenced record)
    1 — new runtime dep added without a record
    2 — invocation error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_PYPROJECT = ROOT / "packages" / "core" / "pyproject.toml"
LIBRARIES_MD = ROOT / ".specify" / "memory" / "libraries.university"
DECISIONS_DIR = ROOT / "specs" / "002-rewrite-foundation" / "decisions"

REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-")


def _runtime_deps_from_pyproject_text(text: str) -> set[str]:
    data = tomllib.loads(text)
    deps = data.get("project", {}).get("dependencies", []) or []
    out: set[str] = set()
    for dep in deps:
        match = REQ_NAME_RE.match(str(dep))
        if match:
            out.add(_normalize(match.group(1)))
    return out


def _runtime_deps_at_revision(revision: str) -> set[str]:
    proc = subprocess.run(
        ["git", "show", f"{revision}:packages/core/pyproject.toml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # No baseline available (new branch, fresh repo, etc.) — empty baseline.
        return set()
    return _runtime_deps_from_pyproject_text(proc.stdout)


def _libraries_md_mentions(name: str) -> bool:
    if not LIBRARIES_MD.is_file():
        return False
    text = LIBRARIES_MD.read_text().lower()
    return name in text


def _decisions_mention(name: str) -> bool:
    if not DECISIONS_DIR.is_dir():
        return False
    front_matter_re = re.compile(r"^---\s*$.*?^---\s*$", re.MULTILINE | re.DOTALL)
    dep_line_re = re.compile(r"^dependency:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
    for md in DECISIONS_DIR.glob("*.university"):
        text = md.read_text()
        match = front_matter_re.search(text)
        if not match:
            continue
        for dep in dep_line_re.findall(match.group(0)):
            if _normalize(dep) == name:
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--baseline",
        default="main",
        help="Git revision to diff against (default: main).",
    )
    parser.add_argument(
        "--current",
        default=None,
        help="Path to the current pyproject.toml (default: packages/core/pyproject.toml).",
    )
    args = parser.parse_args(argv)

    current_path = Path(args.current) if args.current else CORE_PYPROJECT
    if not current_path.is_file():
        print(f"ERROR: missing {current_path}", file=sys.stderr)
        return 2
    current = _runtime_deps_from_pyproject_text(current_path.read_text())
    baseline = _runtime_deps_at_revision(args.baseline)
    new = sorted(current - baseline)

    if not new:
        print("adopt-vs-build: no new runtime dependencies in arc-guard-core")
        return 0

    missing: list[str] = []
    for dep in new:
        if _libraries_md_mentions(dep) or _decisions_mention(dep):
            continue
        missing.append(dep)

    if missing:
        print("adopt-vs-build: missing adopt-vs-build records for new runtime deps:")
        for dep in missing:
            print(f"  - {dep}")
        print(
            "\nAdd a line to .specify/memory/libraries.university or an ADR under "
            f"{DECISIONS_DIR.relative_to(ROOT)} with front-matter `dependency: <name>`."
        )
        return 1

    print("adopt-vs-build: every new runtime dep has a referenced record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
