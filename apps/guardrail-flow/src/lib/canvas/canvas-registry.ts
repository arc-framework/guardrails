/**
 * Static registry of the architecture canvases the dashboard ships.
 * Vite's JSON import resolves these at build time so the bundle is
 * self-contained — no fetch, no asset path coupling.
 */

import newFlowJson from "../../../canvases/new-flow.canvas.json";
import requestFlowJson from "../../../canvases/request-flow.canvas.json";
import dagJourneyJson from "../../../canvases/request-dag-journey.canvas.json";
import dagBrainJson from "../../../canvases/request-dag-brain.canvas.json";
import pipelineMetroJson from "../../../canvases/pipeline-metro.canvas.json";
import pipelineSwimlaneJson from "../../../canvases/pipeline-swimlane.canvas.json";
import requestFlowTreeJson from "../../../canvases/request-flow-tree.canvas.json";
import type { CanvasFile } from "./types";

export interface CanvasRegistryEntry {
  slug: string;
  title: string;
  description: string;
  data: CanvasFile;
  /** True if the canvas's stage nodes can be driven by lifecycle events. */
  ridDrivable: boolean;
}

export const CANVAS_REGISTRY: readonly CanvasRegistryEntry[] = [
  {
    slug: "new-flow",
    title: "New flow — 12-stage pipeline",
    description:
      "The current GuardPipeline. Each stage runs inside stage_runner for uniform span/event/metric emission. Inspectors plug into stage 3 (classify); strategies plug into stage 7 (execute).",
    data: newFlowJson as unknown as CanvasFile,
    ridDrivable: true,
  },
  {
    slug: "request-flow",
    title: "Request flow — four request shapes",
    description:
      "Three live request shapes that hit the running arc-guard-service via /v1/chat/completions: benign chat, PII redaction, and prompt-injection block. The fourth column is the retired /v1/guard lane (now a 410 Gone tombstone) kept as a historical reference. Each column lists every class on the call path top-to-bottom.",
    data: requestFlowJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-dag-journey",
    title: "Request journey — stage gates",
    description:
      "Vertical checkpoint view. Active stages (classify, sanitize, route, execute, backend) are full-height with detail chips. No-op and inert stages appear as thin dividers.",
    data: dagJourneyJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-dag-brain",
    title: "Request brain map — radial DAG",
    description:
      "RequestStarted at the center; parent_id edges branch outward to four arms: pre-process (left), backend (right), completion (below). Cross-ref edges show finding_id and swap_origin_id causal links.",
    data: dagBrainJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "pipeline-metro",
    title: "Pipeline — metro map",
    description:
      "12 stages as subway stations on a horizontal line. The line splits at execute: the red line (blocked) runs above to refusal; the blue line (pass) runs below through verify and rehydrate. Inspectors and strategies hang below their station.",
    data: pipelineMetroJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "pipeline-swimlane",
    title: "Pipeline — swimlane flowchart",
    description:
      "Three horizontal lanes: OBSERVABILITY (stage_runner hooks) · PIPELINE (12 stages with branch at execute) · PLUGINS (inspectors, strategies, reporters). Compact left-to-right read.",
    data: pipelineSwimlaneJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-flow-tree",
    title: "Request flow — decision tree",
    description:
      "All traffic enters one endpoint; classify branches into three paths based on findings. Read top-to-bottom within each column: benign (pass), PII (redact), injection (block). /v1/guard shown as a retired tombstone.",
    data: requestFlowTreeJson as unknown as CanvasFile,
    ridDrivable: false,
  },
];

export function getCanvasBySlug(slug: string): CanvasRegistryEntry | undefined {
  return CANVAS_REGISTRY.find((c) => c.slug === slug);
}
