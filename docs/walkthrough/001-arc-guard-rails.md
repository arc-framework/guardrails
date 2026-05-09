# 001 — arc-guard-rails

## Goal

Build `arc-guard` as an in-process Python guardrails library for LLM workflows that can sanitize sensitive data, detect prompt attacks, and expose a reusable pipeline with optional adapters.

## Scope

- Core Python guardrail package under `python/arc-guardrails/`.
- Replace Sherlock's inline regex guard with `GuardPipeline`.
- Support optional integrations such as NATS, Unleash, webhook reporting, and OTEL.
- Keep the core usable outside ARC infrastructure.

## Core architecture

- Protocol-first design with explicit interfaces for guard, inspector, strategy, reporter, flag provider, middleware, and entity provider.
- `GuardPipeline` orchestrates inspectors and action strategies.
- Baseline inspectors include injection, Presidio-based entity detection, semantic inspection, and custom registry-backed patterns.
- Optional adapters provide infrastructure integration without making the core package depend on ARC services.

## Key quality constraints

- Python 3.11+.
- `ruff`, `mypy`, and `pytest` are baseline quality gates.
- Fail-open behavior for inspector errors.
- Bounded, non-blocking reporter behavior.
- Keep the core package decoupled from provider-specific runtime dependencies.

## Current status

- The baseline library shape, protocol design, and integration intent are already documented in the spec and implementation plan.
- The rewrite roadmap now narrows the thesis emphasis toward enterprise prompt/response guardrailing, semantic fidelity, and safe rehydration.
- The next architecture step is package restructuring and policy-driven pipeline composition.

## Next step

- Use the rewrite roadmap to convert the current single-package structure into cleaner package boundaries.
- Keep this walkthrough updated as the spec evolves toward intent-preserving guardrailing and stronger research evaluation.