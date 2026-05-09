/**
 * Static registry of the 3 architecture canvases the dashboard ships.
 * Vite's JSON import resolves these at build time so the bundle is
 * self-contained — no fetch, no asset path coupling.
 */

import newFlowJson from "../../../canvases/new-flow.canvas.json";
import requestFlowJson from "../../../canvases/request-flow.canvas.json";
import requestDagJson from "../../../canvases/request-dag-sample.canvas.json";
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
    slug: "request-dag-sample",
    title: "Request DAG — lifecycle event model",
    description:
      "One PII-redaction request rendered as the DAG the lifecycle sink emits. Every event the sink fires is a node; parent_id pointers are edges.",
    data: requestDagJson as unknown as CanvasFile,
    ridDrivable: false,
  },
];

export function getCanvasBySlug(slug: string): CanvasRegistryEntry | undefined {
  return CANVAS_REGISTRY.find((c) => c.slug === slug);
}
