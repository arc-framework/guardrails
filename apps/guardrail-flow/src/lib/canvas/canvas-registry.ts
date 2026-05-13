/**
 * Static registry of the architecture canvases the dashboard ships.
 * Vite's JSON import resolves these at build time so the bundle is
 * self-contained — no fetch, no asset path coupling.
 */

import pipelineSwimlaneJson from "../../../canvases/pipeline-swimlane.canvas.json";
import requestDagBenignJson from "../../../canvases/request-dag-benign.canvas.json";
import requestDagPiiJson from "../../../canvases/request-dag-pii.canvas.json";
import requestDagBlockJson from "../../../canvases/request-dag-block.canvas.json";
import requestFlowJson from "../../../canvases/request-flow.canvas.json";
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
    slug: "pipeline-swimlane",
    title: "Architecture — 12-stage pipeline",
    description:
      "High-level architecture diagram. Three horizontal lanes: OBSERVABILITY (stage_runner hooks) · PIPELINE (12 stages with branch at execute) · PLUGINS (inspectors, strategies, reporters).",
    data: pipelineSwimlaneJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-dag-benign",
    title: "UC1 · Benign chat — request DAG",
    description:
      "All inspectors clean — 0 findings. Route decides action = pass. Backend called with the original payload unchanged. No redaction, no block.",
    data: requestDagBenignJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-dag-pii",
    title: "UC2 · PII redaction — request DAG",
    description:
      "Presidio flags EMAIL_ADDRESS HIGH. Sanitize replaces the span. Backend receives the redacted payload. action = redact, blocked = false.",
    data: requestDagPiiJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-dag-block",
    title: "UC3 · Injection block — request DAG",
    description:
      "InjectionInspector fires PROMPT_INJECTION CRITICAL. Route short-circuits to refusal. Backend is never called. action = block, blocked = true.",
    data: requestDagBlockJson as unknown as CanvasFile,
    ridDrivable: false,
  },
  {
    slug: "request-flow",
    title: "Request flow — four request shapes",
    description:
      "Three live request shapes that hit the running arc-guard-service via /v1/chat/completions: benign chat, PII redaction, and prompt-injection block. The fourth column is the retired /v1/guard lane (now a 410 Gone tombstone) kept as a historical reference.",
    data: requestFlowJson as unknown as CanvasFile,
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
