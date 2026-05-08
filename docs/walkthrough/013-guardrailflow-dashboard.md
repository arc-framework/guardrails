# Walkthrough — Spec 013: GuardRailFlow Dashboard

This page is the operator-facing summary of [Spec 013](../../specs/013-guardrailflow-dashboard/spec.md). It documents the Vite-based GuardRailFlow application that sits on top of the backend data plane and turns request replay, DecisionRecord detail, and debug data into a usable operator dashboard.

## What changed

Four additive deliverables are planned:

| Deliverable                                                                                             | Where                                             |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `apps/guardrail-flow/` Vite + React + TypeScript app                                                    | planned new app path outside the Python workspace |
| `/requests` explorer with pagination, filtering, and live-request affordances                           | planned in the dashboard app                      |
| `/requests/:rid` workspace with lifecycle graph, right-side inspector, and bottom debug console         | planned in the dashboard app                      |
| Fixture mode and environment-configurable backend URL so the app can run with or without a live backend | planned in the dashboard app                      |

This spec is explicitly **not** a Next.js app and does not introduce a Node backend-for-frontend layer.

## Why

The user chose Vite as the dashboard base. That means the Python service must own the backend data plane and the UI must stay a pure client. This split makes shipping faster: the app focuses on table, canvas, decision, and debug UX instead of re-implementing backend logic.

The dashboard is also more than a demo. It is the operator-facing way to answer two questions fast:

- what path did this request take?
- why did the system choose that path?

## Public surface

Planned user-visible surfaces:

| Surface              | Notes                                              |
| -------------------- | -------------------------------------------------- |
| `/requests`          | Request Explorer                                   |
| `/requests/:rid`     | Request Workspace                                  |
| right-side inspector | Stage / Decision / Policy / JSON views             |
| bottom debug console | Lifecycle SSE / Logs / Backend / Diff-Replay views |
| fixture mode         | Run the app without a live backend                 |

## Operator knobs

Planned knobs for the app surface:

| Knob               | Purpose                                                         |
| ------------------ | --------------------------------------------------------------- |
| backend base URL   | Point the Vite app at the target Python service                 |
| fixture mode       | Local demo / design mode without backend dependencies           |
| layout preferences | Persist explorer / inspector / debug-pane sizing and visibility |

The app inherits backend payload-safety rules; it does not create a richer raw-data surface than the service exposes.

## References

- [Spec 013 — full specification](../../specs/013-guardrailflow-dashboard/spec.md)
- [Spec 012 — backend data plane](../../specs/012-dashboard-backend-data-plane/spec.md)
- [Spec 010 — lifecycle substrate](../../specs/010-lifecycle-sink/spec.md)
- [Scratch source](../superpowers/specs/2026-05-08-dashboard-data-coverage-scratch.md)
