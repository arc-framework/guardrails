# Canvas Refresh Changelog — 2026-05-09

This document records every canvas file that was modified during the 2026-05-09 knowledge-base build and canvas refresh, the evidence for each change, and the semantic graph source that backs it.

## Context

All canvases in `docs/canvases/` were cross-checked against the knowledge base constructed from the GitNexus semantic graph (guardrails, 9,374 symbols, 14,073 edges, 103 flows, indexed 2026-05-09) and the walkthrough docs under `docs/walkthrough/`.

`docs/canvases/` is the source of truth. All changes were synced to `apps/guardrail-flow/canvases/` via `scripts/sync-canvases.sh` after the edits.

---

## `docs/canvases/new-flow.canvas`

### 1. Replaced `CustomInspector` with SQL and Shell injection inspectors

**Node changed:** `i_cust` → `i_sql` + `i_shell`

**Before:**

```
CustomInspector · inspectors/custom.py
```

**After:**

```
SqlInjectionInspector · inspectors/sql_injection.py
ShellInjectionInspector · inspectors/shell_injection.py
```

**Evidence:** `docs/knowledge-base/01-architecture/inspection-subsystem.md` — the concrete inspector table lists `SqlInjectionInspector` and `ShellInjectionInspector` as distinct implementations added with the detection-extensibility work (spec 011). `CustomInspector` was a placeholder that never shipped as a named class.

**Edges updated:** `p_cust` → `p_sql` + `p_shell` (both from `s_classify`).

**Group updated:** `grp_inspectors` height expanded from 662 to 780 to accommodate two nodes + repositioned `i_jb` (shifted down 100px).

---

### 2. Added `LifecycleSink` to the per-stage hooks group

**Node added:** `h_lifecycle`

```
LifecycleSink · arc_guard_core.lifecycle.sink
29 typed frozen events per request; parent-id DAG
→ RingBufferLifecycleSink (dev) · SqliteLifecycleSink (prod)
→ BroadcastingLifecycleSink for SSE fan-out
```

**Evidence:** `docs/knowledge-base/01-architecture/observability.md` — the four independent observability surfaces are Logger, Tracer, MetricSink, and LifecycleSink. The canvas previously showed only three hooks (Tracer, Logger, MetricSink). LifecycleSink is the fourth surface added in the lifecycle event substrate work.

**Group updated:** `grp_hooks` height expanded from 662 to 780.

**Edge added:** `h_to_lifecycle` (from `h_lifecycle` to `s_sanitize`, labeled "every stage").

---

### 3. Fixed inspector count in `note_summary`

**Before:** `3 inspectors + 5 strategies + ...`

**After:** `5 inspectors (Presidio, Regex injection, SQL injection, Shell injection, Jailbreak) + 5 strategies + ...`

**Evidence:** Same as change 1 — concrete inspector count is now 5 (plus ConversationTurnInspector which runs in a separate stage).

---

## `docs/canvases/request-flow.canvas`

### 1. Fixed factual error in use case 3 — PresidioInspector attribution

**Node changed:** `u3_pres`

**Before:**

```
PresidioInspector — adds JAILBREAK_DIRECT_OVERRIDE finding
```

**After:**

```
PresidioInspector — no PII/PCI found; runs independently of injection detectors
```

**Evidence:** `docs/knowledge-base/01-architecture/inspection-subsystem.md` — Presidio is a NER inspector that detects PII and PCI entities (PERSON, CREDIT_CARD, EMAIL_ADDRESS, etc.). It does not produce jailbreak findings. The `JAILBREAK_DIRECT_OVERRIDE` entity type is produced by the `JailbreakDetector` (shown separately as `i_jb` / `RuleBasedJailbreakDetector`). The original canvas was conflating two separate inspector calls.

---

### 2. Added LifecycleSink to cross-flow sinks summary

**Node changed:** `sinks_summary`

**Added to "Wired sinks" section:**

```
SqliteLifecycleSink + BroadcastingLifecycleSink (spec 010) → 29 typed events per request;
SSE /events for live dashboards; GET /lifecycle/{rid} for replay
```

**Evidence:** `docs/knowledge-base/01-architecture/lifecycle-sink.md` — the lifecycle sink is now a wired, production observability surface in `arc-guard-service`. The canvas's cross-flow summary only listed LogReporter and StdlibBridgeLogger; the LifecycleSink is the primary structured audit surface.

---

## `docs/canvases/request-dag-sample.canvas`

### 1. Updated `gaps_panel` — marked all spec 010 events as implemented

**Before:** All 9 event types in the gaps table were listed as "NOT emitted" with implementation instructions.

**After:** Table restructured into two sections:

- **Implemented (spec 010):** InspectorRan, FindingProduced, SanitizationApplied, PolicyResolved, StrategyExecuted, PayloadRewritten, BackendCalled/BackendResponded, ResponseAssembled, ReportFlushed — all 9 marked ✅
- **Still open (phase 2):** InspectorMatchExplain, PlaceholderMapBuilt, PolicyRuleEvaluated (per-rule chain), RehydrationVerified (rejection detail), InspectorFailed — 5 deferred events that were explicitly out of scope for the lifecycle sink implementation

**Evidence:** `docs/walkthrough/010-lifecycle-sink.md` describes the 29 typed events shipped with the lifecycle sink. The `request-dag-sample.canvas` was originally a planning document; it now functions as a reference document and must reflect what was actually built.

---

### 2. Updated `storage_panel` — marked SQLite as implemented

**Before:** SQLite described as "recommended for replay across restart" (prospective).

**After:** Marked as "✅ implemented (spec 010)" with schema v2 detail: 4 tables (`lifecycle_events`, `request_summaries`, `decision_records`, `debug_entries`), WAL mode, retention GC.

**Evidence:** `docs/knowledge-base/03-decisions/sqlite-lifecycle-sink.md` — the ADR documents SQLite as the accepted and implemented storage backend.

---

## `apps/guardrail-flow/canvases/` — derived copy

All three canvas files were synced to the app directory immediately after the docs/ changes:

```
scripts/sync-canvases.sh
  OK    new-flow
  OK    request-flow
  OK    request-dag-sample
```

JSON validity confirmed before sync via `python3 -c "import json; json.load(open(f))"` for all three files.

---

## Files Not Changed

| Canvas                          | Reason                                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `docs/canvases/old-flow.canvas` | Intentionally excluded — represents the pre-rewrite architecture; excluded from the app registry |

---

## Archive

Pre-change copies of all canvas files are preserved at `docs/canvases/_archive/2026-05-09/` (archived at the start of this session before any modifications).
