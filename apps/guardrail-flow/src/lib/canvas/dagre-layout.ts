/**
 * Layout helpers for the "Spread" button.
 *
 * Two modes:
 *
 *   - `spreadLayout` — scale-outward: keep the hand-tuned topology and
 *     orientation, just multiply each node's distance from the centroid by
 *     a factor so cards stop overlapping. The default. Ships in the UI.
 *   - `dagreLayout`  — full topological re-layout via @dagrejs/dagre. Kept
 *     around for completeness (and in case a future spec wants strict
 *     topological view), but NOT wired into the toolbar today because it
 *     flips orientation (an LR canvas comes back as TB or vice versa) and
 *     operators expect orientation to be preserved.
 *
 * Both helpers skip group nodes during layout and rebuild group bounding
 * boxes afterwards from the same children that lived inside them
 * originally. That preserves the labelled-container semantics regardless
 * of which mode the operator picks.
 */

import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "reactflow";

export type LayoutDirection = "TB" | "LR";

export interface LayoutOptions {
  direction?: LayoutDirection;
  ranksep?: number;
  nodesep?: number;
}

const DEFAULT_OPTS: Required<LayoutOptions> = {
  direction: "TB",
  ranksep: 90,
  nodesep: 60,
};

/**
 * Scale-outward spread. Pushes every node away from the centroid by
 * `factor` (default 1.4×). Topology and orientation are preserved — the
 * canvas keeps its left-to-right or top-to-bottom flow exactly as drawn,
 * cards just have more breathing room.
 */
export function spreadLayout(
  nodes: Node[],
  edges: Edge[],
  factor = 1.4,
): { nodes: Node[]; edges: Edge[] } {
  const layoutNodes = nodes.filter((n) => n.type !== "canvasGroup");
  const groupNodes = nodes.filter((n) => n.type === "canvasGroup");

  if (layoutNodes.length === 0) return { nodes, edges };

  // Centroid in node-center coordinates so we scale around the visual
  // middle, not the top-left of an arbitrary bounding box.
  let cx = 0;
  let cy = 0;
  for (const n of layoutNodes) {
    const w = (n.style?.width as number) ?? 0;
    const h = (n.style?.height as number) ?? 0;
    cx += n.position.x + w / 2;
    cy += n.position.y + h / 2;
  }
  cx /= layoutNodes.length;
  cy /= layoutNodes.length;

  const positionedNodes: Node[] = layoutNodes.map((n) => {
    const w = (n.style?.width as number) ?? 0;
    const h = (n.style?.height as number) ?? 0;
    const center = { x: n.position.x + w / 2, y: n.position.y + h / 2 };
    const scaled = {
      x: cx + (center.x - cx) * factor,
      y: cy + (center.y - cy) * factor,
    };
    return {
      ...n,
      position: { x: scaled.x - w / 2, y: scaled.y - h / 2 },
    };
  });

  const positionedById = new Map(positionedNodes.map((n) => [n.id, n]));
  const repositionedGroups = groupNodes.map((group) => rewrapGroup(group, nodes, positionedById));

  return {
    nodes: [...repositionedGroups, ...positionedNodes],
    edges,
  };
}

/**
 * Topological re-layout via dagre. NOT used by the toolbar today — kept
 * for tools that want strict rank-based ordering (e.g. a future "Compact"
 * mode). Flips orientation to dagre's preferred direction, which is why
 * we don't ship it as the spread default.
 */
export function dagreLayout(
  nodes: Node[],
  edges: Edge[],
  opts: LayoutOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  const { direction, ranksep, nodesep } = { ...DEFAULT_OPTS, ...opts };

  const g = new dagre.graphlib.Graph({ compound: false });
  g.setGraph({ rankdir: direction, ranksep, nodesep });
  g.setDefaultEdgeLabel(() => ({}));

  // Skip group nodes — they're not real participants. We rebuild their
  // bounding boxes after layout completes.
  const layoutNodes = nodes.filter((n) => n.type !== "canvasGroup");
  const groupNodes = nodes.filter((n) => n.type === "canvasGroup");

  for (const node of layoutNodes) {
    const width = (node.style?.width as number) ?? 200;
    const height = (node.style?.height as number) ?? 80;
    g.setNode(node.id, { width, height });
  }

  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  const positionedNodes: Node[] = layoutNodes.map((node) => {
    const layout = g.node(node.id);
    const width = (node.style?.width as number) ?? 200;
    const height = (node.style?.height as number) ?? 80;
    return {
      ...node,
      position: {
        x: layout.x - width / 2,
        y: layout.y - height / 2,
      },
    };
  });

  // For groups, derive the new bounding box from the laid-out children.
  // Heuristic: a group encloses the layout nodes whose original positions
  // fell within its original rect. After spread, those same nodes should
  // be enclosed by a bounding box around their new positions.
  const positionedById = new Map(positionedNodes.map((n) => [n.id, n]));
  const repositionedGroups = groupNodes.map((group) => rewrapGroup(group, nodes, positionedById));

  return {
    nodes: [...repositionedGroups, ...positionedNodes],
    edges,
  };
}

function rewrapGroup(group: Node, originalNodes: Node[], positionedById: Map<string, Node>): Node {
  const groupX = group.position.x;
  const groupY = group.position.y;
  const groupW = (group.style?.width as number) ?? 0;
  const groupH = (group.style?.height as number) ?? 0;

  // Find children of this group based on the original layout: children are
  // text nodes whose original rect is fully inside the group's rect.
  const children = originalNodes.filter((n) => {
    if (n.type === "canvasGroup") return false;
    const w = (n.style?.width as number) ?? 0;
    const h = (n.style?.height as number) ?? 0;
    const cx0 = n.position.x;
    const cy0 = n.position.y;
    const cx1 = cx0 + w;
    const cy1 = cy0 + h;
    return cx0 >= groupX && cy0 >= groupY && cx1 <= groupX + groupW && cy1 <= groupY + groupH;
  });

  if (children.length === 0) {
    return group;
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const c of children) {
    const positioned = positionedById.get(c.id);
    if (!positioned) continue;
    const px = positioned.position.x;
    const py = positioned.position.y;
    const pw = (positioned.style?.width as number) ?? 0;
    const ph = (positioned.style?.height as number) ?? 0;
    minX = Math.min(minX, px);
    minY = Math.min(minY, py);
    maxX = Math.max(maxX, px + pw);
    maxY = Math.max(maxY, py + ph);
  }

  if (minX === Infinity) return group;

  const padding = 24;
  const newX = minX - padding;
  const newY = minY - padding;
  const newW = maxX - minX + padding * 2;
  const newH = maxY - minY + padding * 2;

  return {
    ...group,
    position: { x: newX, y: newY },
    style: { ...group.style, width: newW, height: newH },
    data: { ...(group.data as Record<string, unknown>), width: newW, height: newH },
  };
}
