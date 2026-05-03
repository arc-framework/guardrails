"""CLI batch wrapper: read GuardInput JSONL, write GuardResult JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from arc_guard_core.types import GuardInput

from arc_guard_service import run_guard


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arc-guard-batch",
        description="Run arc-guard against JSONL inputs.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to JSONL input. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to JSONL output. Writes stdout when omitted.",
    )
    return parser


def _open_input(path: str | None):
    if path is None or path == "-":
        return sys.stdin
    return Path(path).open("r", encoding="utf-8")


def _open_output(path: str | None):
    if path is None or path == "-":
        return sys.stdout
    return Path(path).open("w", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    inp = _open_input(args.input)
    out = _open_output(args.output)
    try:
        for line in inp:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            result = run_guard(GuardInput(text=payload["text"]))
            out.write(json.dumps(asdict(result), default=str) + "\n")
    finally:
        if args.input not in (None, "-"):
            inp.close()
        if args.output not in (None, "-"):
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
