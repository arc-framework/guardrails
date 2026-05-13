# Canvases

Obsidian Canvas files for understanding the arc-guardrails code structure.

| File | Shows |
|---|---|
| `old-flow.canvas` | The pre-rewrite single-pass pipeline. 4 inspectors → 3 strategies → 4 reporters → result. Adapters (NATS, Unleash) lived inside the SDK. Sourced from the recovered deprecation README + the arc-platform GUARD-RAIL ARD. |
| `new-flow.canvas` | The current 12-stage pipeline. Each stage wrapped by `stage_runner` for uniform span/event/metric emission. Inspectors plug into stage 3 (classify); strategies plug into stage 7 (execute); research subpackages (intent / fidelity / rehydration / deception / jailbreak) own their own stages. Adapters moved to backlog §4.2 to keep the SDK provider-neutral. |
| `request-flow.canvas` | Four real request shapes that hit the running `arc-guard-service` — benign chat, PII redaction, prompt-injection block, and the generic `/v1/guard` direct call. Each column lists every class on the call path top-to-bottom (HTTP → schemas → pipeline → inspectors → strategies → sinks → response). Inert sinks (`NullMetricSink`, `NullTracer`) and other architectural gaps are flagged in red so the canvas doubles as a punch list for what to wire next. |
| `request-dag-sample.canvas` | One PII-redaction request rendered as the DAG the proposed lifecycle sink would emit. Every event the sink fires is a node; parent_id pointers are edges. Right-side panels show the typed event models (pseudo-Python), the events the SDK doesn't emit today (5 of 13 are net-new), and the deeper "agent brain" introspection events that would land in a phase-2 spec. Bottom panel discusses storage choice (RingBuffer / SQLite / external). Use this to validate whether the sink data model is sufficient for the dashboard's graph view. |

## How to view

Open this directory as an Obsidian vault (or open the parent repo as a vault). Both `.canvas` files render as visual whiteboards. Drag, regroup, add notes, draw new edges — they're meant to be edited as you reason about the flow.

## Color legend (consistent across both canvases)

- **Cyan (5)** — pipeline endpoints + stage cards
- **Green (4)** — Inspectors
- **Purple (6)** — Strategies and research subpackages (IntentEncoder, FidelityScorer, etc.)
- **Orange (2)** — Reporters and observability hooks (Tracer / Logger / MetricSink)
- **Yellow (3)** — Flag providers, registry helpers, summary notes
- **Red (1)** — Dropped / backlog items, refusal branch
