/**
 * Convert a JSON-Canvas file into React Flow `nodes` + `edges`. The original
 * Obsidian coordinates pass through unchanged so the hand-tuned layout is
 * preserved by default; the spread button (dagre) recomputes positions.
 *
 * Rendering details:
 *
 * - Group nodes are emitted with `type: "canvasGroup"` and a higher `zIndex`
 *   so they render *behind* their children. React Flow doesn't enforce
 *   DOM-order containment for groups outside its first-class group system,
 *   but the visual appearance — translucent labelled rectangle behind text
 *   nodes — is achieved through z-index + larger size.
 * - Text nodes become `type: "canvasText"` with the markdown-ish body and
 *   color band passed through as data.
 * - Edges fan out to a custom `type: "canvasEdge"` so we can color-band them
 *   the same way nodes are color-banded and animate them on playback.
 */

import type { Edge, Node, Position } from "reactflow";
import type { CanvasEdge, CanvasFile, CanvasGroupNode, CanvasSide, CanvasTextNode } from "./types";

export interface CanvasTextNodeData {
  text: string;
  color?: string;
}

export interface CanvasGroupNodeData {
  label: string;
  color?: string;
  width: number;
  height: number;
}

export interface CanvasEdgeData {
  label?: string;
  color?: string;
  active: boolean;
}

const SIDE_TO_POSITION: Record<CanvasSide, Position> = {
  top: "top" as Position,
  right: "right" as Position,
  bottom: "bottom" as Position,
  left: "left" as Position,
};

export interface ParsedCanvas {
  nodes: Node[];
  edges: Edge[];
}

export function parseCanvas(file: CanvasFile): ParsedCanvas {
  const groupNodes: Node<CanvasGroupNodeData>[] = file.nodes
    .filter((n): n is CanvasGroupNode => n.type === "group")
    .map((g) => ({
      id: g.id,
      type: "canvasGroup",
      position: { x: g.x, y: g.y },
      style: { width: g.width, height: g.height, zIndex: -1 },
      data: { label: g.label, color: g.color, width: g.width, height: g.height },
      draggable: false,
      selectable: false,
      // React Flow puts higher zIndex on top; we explicitly want groups
      // *behind* the text nodes that visually live inside them, so a
      // negative-bias zIndex on the wrapper plus a positive bias on text
      // nodes (below) gives the right stacking.
      zIndex: -1,
    }));

  const textNodes: Node<CanvasTextNodeData>[] = file.nodes
    .filter((n): n is CanvasTextNode => n.type === "text")
    .map((t) => ({
      id: t.id,
      type: "canvasText",
      position: { x: t.x, y: t.y },
      style: { width: t.width, height: t.height },
      data: { text: t.text, color: t.color },
      zIndex: 1,
    }));

  const edges: Edge<CanvasEdgeData>[] = file.edges.map((e: CanvasEdge) => ({
    id: e.id,
    source: e.fromNode,
    target: e.toNode,
    sourceHandle: e.fromSide ? `out-${e.fromSide}` : undefined,
    targetHandle: e.toSide ? `in-${e.toSide}` : undefined,
    type: "canvasEdge",
    label: e.label,
    data: { label: e.label, color: e.color, active: false },
    sourcePosition: e.fromSide ? SIDE_TO_POSITION[e.fromSide] : undefined,
    targetPosition: e.toSide ? SIDE_TO_POSITION[e.toSide] : undefined,
  }));

  return {
    // Groups first so React Flow paints them before children.
    nodes: [...groupNodes, ...textNodes],
    edges,
  };
}
