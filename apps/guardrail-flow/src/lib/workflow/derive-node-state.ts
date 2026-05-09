/**
 * Pure function: lifecycle event stream → per-stage WorkflowNodeState map.
 *
 * Strategy:
 *
 * - Start with all 12 canonical stages in the `inactive` state.
 * - Walk events in `seq` order. `StageRan` events drive state transitions
 *   on their target stage:
 *     - status === "ok"      → completed
 *     - status === "err"     → errored
 *     - status === "skipped" → skipped
 * - Conditional events refine the state of their owning stage:
 *     - JailbreakDetected   → defend.jailbreakHit
 *     - DeceptionScored     → deception_inspect.deceptionScore
 *     - FindingProduced     → classify.findingCount++
 *     - RefusalProduced     → refusal stage flips to `blocked` (terminal)
 * - The "currently executing" stage (only meaningful in live mode) is
 *   the one whose `*Started` event has fired but whose `StageRan` has
 *   not — represented as `active`.
 */

import type { LifecycleEventBase, StageName } from "@/types/api";
import type { WorkflowNodeState } from "@/types/workflow";
import { CANONICAL_STAGES } from "./canonical-graph";

function emptyState(stage: StageName): WorkflowNodeState {
  return {
    stage,
    state: "inactive",
    durationMs: null,
    findingCount: 0,
    jailbreakHit: false,
    deceptionScore: null,
  };
}

function initialMap(): Record<StageName, WorkflowNodeState> {
  const out = {} as Record<StageName, WorkflowNodeState>;
  for (const s of CANONICAL_STAGES) {
    out[s] = emptyState(s);
  }
  return out;
}

export function deriveNodeStates(
  events: LifecycleEventBase[],
): Record<StageName, WorkflowNodeState> {
  const out = initialMap();

  // Sort defensively — events SHOULD already be in seq order from the
  // backend, but a merged stream (replay + live SSE) might be out of
  // order temporarily.
  const ordered = [...events].sort((a, b) => a.seq - b.seq);

  for (const ev of ordered) {
    const et = ev.event_type;

    if (et === "StageRan") {
      const stage = (ev as { stage?: StageName }).stage;
      if (stage && stage in out) {
        const status = (ev as { status?: string }).status ?? "ok";
        const durationMs = (ev as { duration_ms?: number }).duration_ms ?? null;
        const node = out[stage];
        node.durationMs = durationMs;
        if (status === "ok") {
          node.state = "completed";
        } else if (status === "err") {
          node.state = "errored";
        } else if (status === "skipped") {
          node.state = "skipped";
        }
      }
      continue;
    }

    if (et === "JailbreakDetected") {
      out.defend.jailbreakHit = true;
      continue;
    }

    if (et === "DeceptionScored") {
      const v = (ev as { score_value?: number | null }).score_value ?? null;
      out.deception_inspect.deceptionScore = v;
      continue;
    }

    if (et === "FindingProduced") {
      out.classify.findingCount += 1;
      continue;
    }

    if (et === "RefusalProduced") {
      out.refusal.state = "blocked";
      continue;
    }
  }

  return out;
}
