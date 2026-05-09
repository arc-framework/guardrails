/**
 * Subset of the JSON-Canvas spec we render. Obsidian Canvas files use this
 * shape; we only emit `text` and `group` nodes — other node types in the
 * spec (`file`, `link`) aren't used by any of the 3 canvases the dashboard
 * ships and would need new node-renderer components if they ever are.
 */

export type CanvasColor = "1" | "2" | "3" | "4" | "5" | "6" | string;
export type CanvasSide = "top" | "right" | "bottom" | "left";

export interface CanvasTextNode {
  id: string;
  type: "text";
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color?: CanvasColor;
}

export interface CanvasGroupNode {
  id: string;
  type: "group";
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color?: CanvasColor;
}

export type CanvasNode = CanvasTextNode | CanvasGroupNode;

export interface CanvasEdge {
  id: string;
  fromNode: string;
  toNode: string;
  fromSide?: CanvasSide;
  toSide?: CanvasSide;
  color?: CanvasColor;
  label?: string;
}

export interface CanvasFile {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

/**
 * Stage-id mapping: canvas node ids in `new-flow.canvas` → backend
 * StageName values from lifecycle events. Only used by the new-flow canvas
 * to drive rid-based active-flow animation; the other 2 canvases don't
 * have a 1:1 correspondence to lifecycle events.
 */
export const NEW_FLOW_STAGE_ID_TO_BACKEND_STAGE: Record<string, string> = {
  s_validate: "validate",
  s_defend: "defend",
  s_classify: "classify",
  s_decept: "deception_inspect",
  s_sanitize: "sanitize",
  s_route: "route",
  s_execute: "execute",
  s_refusal: "refusal",
  s_verify: "verify",
  s_rehyd: "rehydrate",
  s_decemit: "decision_emit",
  s_report: "report",
};
