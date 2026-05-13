# Walkthrough — Spec 007: Integration, API, and Documentation Completion

> **Note (2026-05-09):** `POST /v1/guard` was retired in [Spec 014](../../specs/014-pipeline-instrumentation-completion/spec.md). The route is now a tombstone returning HTTP 410 Gone with a pointer envelope to `POST /v1/chat/completions`. Use the chat-completions endpoint for full-pipeline behavior; it runs the same `GuardPipeline.pre_process` + `post_process` semantics this walkthrough describes. Sections referencing `/v1/guard` below are kept for historical context.

This page is the operator-facing summary of [Spec 007](../../specs/007-integration-api-delivery/spec.md). It documents the API package's first non-stub release, the public-surface manifest that downstream operators pin against, and the consolidated doc tree under `docs/architecture/`. (The four integration-mode examples originally shipped with this spec under `examples/` were retired in a later cleanup; integration patterns are documented in prose in `docs/architecture/` instead.)

## What changed

Five deliverables, all additive:

| Deliverable | Where |
|---|---|
| `arc-guard-service` (the `packages/api/` package) gains its first non-stub release with an in-process `run_guard()` adapter, a `python -m arc_guard_service` CLI, and a single-endpoint `POST /v1/guard` HTTP transport under the `[fastapi]` extra | [`packages/api/src/arc_guard_service/`](../../packages/api/src/arc_guard_service/) |
| Public-surface manifest enumerating every Stable / Provisional / Experimental / Internal symbol across the three packages, with a CI drift check (`tools/check_public_surface.py`) | [`docs/public-surface.md`](../public-surface.md) |
| Walkthroughs refreshed to a uniform 5-section schema; new entry for Spec 007 | [`docs/walkthrough/`](.) |
| Architecture index consolidating cross-cutting references | [`docs/architecture/`](../architecture/) |

The decision contract from Specs 002–006 is **frozen**. Spec 007 ships exactly two new public types: `RefusalCode.API_TRANSPORT_TIMEOUT` (one new enum member) and `TransportError(PipelineError)` (one new exception leaf with a matching `FAIL_RULE` row).

## Why

Without Spec 007, the rewrite ships as five packages of contracts that can only be consumed from Python. The "one contract many modes" constitution principle requires at least the SDK + sidecar + CLI + middleware modes to demonstrably share `GuardPipeline.pre_process` semantics. Spec 007 makes that real by shipping `arc-guard-service` with an in-process adapter, a CLI entrypoint, and an HTTP transport — operators can integrate via any of the three modes against the same `GuardPipeline.pre_process` semantics.

The public-surface manifest exists because pre-1.0 packages otherwise leak implicit-stability promises through `__all__` lists. The manifest makes the contract explicit: pin to Stable, evaluate Provisional, accept change risk on Experimental, and never depend on Internal-importable.

## Public surface

| Symbol | Package | Kind | Band | Notes |
|---|---|---|---|---|
| `run_guard` | `arc_guard_service` | function | Provisional | sync adapter for `GuardPipeline.pre_process` |
| `ServiceSettings` | `arc_guard_service` | class | Provisional | transport-layer config (bind / port / max_request_bytes / request_timeout_seconds / pipeline_factory) |
| `create_app` | `arc_guard_service.transport.http` | function | Provisional | FastAPI factory; lazy-imports `fastapi` |
| `RefusalCode.API_TRANSPORT_TIMEOUT` | `arc_guard_core` | enum_member | Provisional | sibling of `API_INVALID_REQUEST`; emitted by transport-layer timeouts |
| `TransportError` | `arc_guard_core` | class | Provisional | leaf exception (`__failure_mode__='closed'`); transport-layer failures |
| `FAILURE_API_TRANSPORT` | `arc_guard_core` | constant | Provisional | failure-class label string |

The full manifest (140+ entries across the three packages) lives at [`docs/public-surface.md`](../public-surface.md). The CI surface-drift check verifies this list matches `__all__` at runtime; adding a new public name without updating the manifest fails CI.

## Operator knobs

The HTTP transport is configurable via `ServiceSettings`:

| Field | Default | Env var |
|---|---|---|
| `bind` | `127.0.0.1` | `ARC_GUARD_SERVICE_BIND` |
| `port` | `8000` | `ARC_GUARD_SERVICE_PORT` |
| `max_request_bytes` | `65536` (64 KiB) | `ARC_GUARD_SERVICE_MAX_REQUEST_BYTES` |
| `request_timeout_seconds` | `30.0` | `ARC_GUARD_SERVICE_REQUEST_TIMEOUT_SECONDS` |
| `pipeline_factory` | `None` (default `GuardPipeline()`) | `ARC_GUARD_SERVICE_PIPELINE_FACTORY` |
| `log_level` | `INFO` | `ARC_GUARD_SERVICE_LOG_LEVEL` |

Set `pipeline_factory` to a dotted path like `myproject.guard:build_pipeline` to use a custom-configured pipeline (e.g., one with the `[semantic]` extra wired up).

## References

- [Spec 007 — full specification](../../specs/007-integration-api-delivery/spec.md)
- [Spec 007 — implementation plan](../../specs/007-integration-api-delivery/plan.md)
- [Public-surface manifest](../public-surface.md)
- [Architecture index](../architecture/README.md)
- [In-process entrypoint contract](../../specs/007-integration-api-delivery/contracts/in-process-entrypoint.md)
- [HTTP transport contract](../../specs/007-integration-api-delivery/contracts/http-transport.md)
