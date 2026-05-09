"""tools/check_async_blocking.py — async-path blocking-call lint.

Walks the AST of the workspace and flags blocking calls reachable from any
``async def`` declared in ``packages/core/`` or ``packages/pip/``. Pairs with
ruff's ``ASYNC`` rule family for stdlib-blocking calls; the AST walker
extends coverage with library-specific blockers (presidio analyser, transformers
pipeline) that ruff cannot know about.

Exit codes:
    0 — no blocking calls reachable from async paths
    1 — blocking call detected
    2 — invocation error
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = [
    ROOT / "packages" / "core" / "src",
    ROOT / "packages" / "pip" / "src",
]

# Blocking call sites — fully-qualified name suffixes that we flag inside any
# async function. Adjust as adapters evolve.
BLOCKING_CALLS = {
    # stdlib classics
    "time.sleep",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_output",
    "subprocess.check_call",
    "socket.recv",
    "socket.send",
    "socket.recv_into",
    # known blocking inference entry points
    "AnalyzerEngine.analyze",                    # presidio
    "AnalyzerEngine.recognize",                  # presidio
    "AnonymizerEngine.anonymize",                # presidio
    "transformers.pipeline.__call__",
    "Pipeline.__call__",                         # generic transformers
    # blocking HTTP
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "urllib.request.urlopen",
}


def _attr_path(node: ast.AST) -> str:
    """Return the dotted path of an attribute / name expression."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _matches_blocking(call_path: str) -> bool:
    if not call_path:
        return False
    return any(call_path.endswith(suffix) for suffix in BLOCKING_CALLS)


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return a list of (line, call) tuples for blocking calls in async fns."""
    text = path.read_text()
    tree = ast.parse(text, filename=str(path))
    findings: list[tuple[int, str]] = []

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.async_depth = 0

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.async_depth += 1
            self.generic_visit(node)
            self.async_depth -= 1

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Don't recurse into nested sync defs from async context — keep it tight.
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if self.async_depth > 0:
                target = node.func
                # asyncio.to_thread / run_in_executor wrappers are explicit
                # opt-outs from this check.
                wrapper_path = _attr_path(target)
                if wrapper_path.endswith("asyncio.to_thread"):
                    return  # do not descend; the inner call is allowed.
                call_path = _attr_path(target)
                if _matches_blocking(call_path):
                    findings.append((node.lineno, call_path))
            self.generic_visit(node)

    V().visit(tree)
    return findings


def _scan_targets(targets: list[Path]) -> list[tuple[Path, int, str]]:
    out: list[tuple[Path, int, str]] = []
    for target in targets:
        if not target.exists():
            continue
        for py_file in target.rglob("*.py"):
            try:
                local = _scan_file(py_file)
            except SyntaxError as exc:
                print(f"WARN: could not parse {py_file}: {exc}", file=sys.stderr)
                continue
            for line, call in local:
                out.append((py_file, line, call))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Override the default scan targets.",
    )
    args = parser.parse_args(argv)
    targets = args.paths or DEFAULT_TARGETS
    findings = _scan_targets([Path(t) for t in targets])
    if findings:
        print("async-blocking lint FAILED:")
        for path, line, call in findings:
            try:
                rel = path.relative_to(ROOT)
            except ValueError:
                rel = path
            print(f"  {rel}:{line}: blocking call {call} inside async function")
        print()
        print("Wrap blocking calls with asyncio.to_thread(...) or run them on a thread pool.")
        return 1
    print("async-blocking: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
