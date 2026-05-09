/**
 * Map a rid's lifecycle event stream onto the canvas node ids that should
 * light up in order. Returns an array of canvas-node ids representing the
 * executed-path traversal.
 *
 * The mapping is canvas-specific. For the new-flow canvas (which has
 * stage-named nodes like `s_validate`, `s_defend`, etc.), we use the
 * NEW_FLOW_STAGE_ID_TO_BACKEND_STAGE table to invert the lookup. Other
 * canvases that aren't 1:1 with lifecycle events return [].
 */

import type { LifecycleEventBase } from "@/types/api";
import { NEW_FLOW_STAGE_ID_TO_BACKEND_STAGE } from "./types";

export function deriveNewFlowPath(events: LifecycleEventBase[]): string[] {
  if (events.length === 0) return [];

  // Inverse map: backend stage name → canvas node id.
  const inverse: Record<string, string> = {};
  for (const [canvasId, stage] of Object.entries(NEW_FLOW_STAGE_ID_TO_BACKEND_STAGE)) {
    inverse[stage] = canvasId;
  }

  // Walk events in seq order. We're only interested in StageRan events
  // (and the "input" pseudo-node at the start, "result" at the end, since
  // the canvas has those framing nodes too).
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  const path: string[] = ["input"];

  for (const ev of ordered) {
    if (ev.event_type !== "StageRan") continue;
    const stage = (ev as { stage?: string }).stage;
    if (!stage) continue;
    const nodeId = inverse[stage];
    if (nodeId && path[path.length - 1] !== nodeId) {
      path.push(nodeId);
    }
  }

  // If the request reached its end stages, frame with "result".
  const last = path[path.length - 1];
  if (last && (last === "s_report" || last === "s_decemit")) {
    path.push("result");
  }

  return path;
}
