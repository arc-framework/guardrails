"""``python -m arc_guard_service`` and ``arc-guard-service`` CLI entrypoint.

Boots the HTTP transport when the ``[fastapi]`` extra is installed; exits
non-zero with a friendly install hint otherwise.
"""

from __future__ import annotations

import argparse
import sys

from arc_guard_service.settings import ServiceSettings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arc-guard-service",
        description="Boot the arc-guard HTTP service.",
    )
    parser.add_argument("--bind", default=None, help="Network bind address.")
    parser.add_argument("--port", default=None, type=int, help="HTTP listen port.")
    parser.add_argument("--workers", default=1, type=int, help="Uvicorn worker count.")
    parser.add_argument(
        "--config-file",
        default=None,
        help="Optional path to a TOML/YAML overriding ServiceSettings (reserved).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Log level for the structured logger (DEBUG/INFO/WARNING/ERROR).",
    )
    return parser


def _settings_from_args(args: argparse.Namespace) -> ServiceSettings:
    overrides: dict[str, object] = {}
    if args.bind is not None:
        overrides["bind"] = args.bind
    if args.port is not None:
        overrides["port"] = args.port
    if args.log_level is not None:
        overrides["log_level"] = args.log_level
    return ServiceSettings(**overrides)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = _settings_from_args(args)

    try:
        from arc_guard_service.transport.http import create_app
    except ImportError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    try:
        import uvicorn
    except ImportError:
        sys.stderr.write(
            "error: arc-guard-service[fastapi] is not installed. "
            "Install it with: pip install arc-guard-service[fastapi]\n",
        )
        return 2

    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.bind,
        port=settings.port,
        workers=args.workers,
        log_level=settings.log_level.lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
