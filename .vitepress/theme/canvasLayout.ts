import type { Edge, Node } from '@vue-flow/core';

const GROUP_PADDING = 24;

export function fitGroupBounds(nodes: Node[]): Node[] {
  const groupNodes = nodes.filter((node) => node.type === 'canvasGroup');
  const contentNodes = nodes.filter((node) => node.type !== 'canvasGroup');

  if (groupNodes.length === 0 || contentNodes.length === 0) {
    return nodes;
  }

  const positionedById = new Map(contentNodes.map((node) => [node.id, node]));
  const fittedGroups = groupNodes.map((group) =>
    rewrapGroup(group, nodes, positionedById),
  );

  return [...fittedGroups, ...contentNodes];
}

export function spreadLayout(
  nodes: Node[],
  edges: Edge[],
  factor = 1.4,
): { nodes: Node[]; edges: Edge[] } {
  const layoutNodes = nodes.filter((node) => node.type !== 'canvasGroup');
  const groupNodes = nodes.filter((node) => node.type === 'canvasGroup');

  if (layoutNodes.length === 0) {
    return { nodes, edges };
  }

  let centroidX = 0;
  let centroidY = 0;

  for (const node of layoutNodes) {
    const width = getNodeWidth(node);
    const height = getNodeHeight(node);
    centroidX += node.position.x + width / 2;
    centroidY += node.position.y + height / 2;
  }

  centroidX /= layoutNodes.length;
  centroidY /= layoutNodes.length;

  const positionedNodes = layoutNodes.map((node) => {
    const width = getNodeWidth(node);
    const height = getNodeHeight(node);
    const centerX = node.position.x + width / 2;
    const centerY = node.position.y + height / 2;

    return {
      ...node,
      position: {
        x: centroidX + (centerX - centroidX) * factor - width / 2,
        y: centroidY + (centerY - centroidY) * factor - height / 2,
      },
    };
  });

  const positionedById = new Map(
    positionedNodes.map((node) => [node.id, node]),
  );
  const rewrappedGroups = groupNodes.map((group) =>
    rewrapGroup(group, nodes, positionedById),
  );

  return {
    nodes: [...rewrappedGroups, ...positionedNodes],
    edges,
  };
}

function rewrapGroup(
  group: Node,
  originalNodes: Node[],
  positionedById: Map<string, Node>,
): Node {
  const groupX = group.position.x;
  const groupY = group.position.y;
  const groupWidth = getNodeWidth(group);
  const groupHeight = getNodeHeight(group);

  const children = originalNodes.filter((node) => {
    if (node.type === 'canvasGroup') {
      return false;
    }

    const nodeX0 = node.position.x;
    const nodeY0 = node.position.y;
    const nodeX1 = nodeX0 + getNodeWidth(node);
    const nodeY1 = nodeY0 + getNodeHeight(node);

    return (
      nodeX0 >= groupX &&
      nodeY0 >= groupY &&
      nodeX1 <= groupX + groupWidth &&
      nodeY1 <= groupY + groupHeight
    );
  });

  if (children.length === 0) {
    return group;
  }

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const child of children) {
    const positioned = positionedById.get(child.id);

    if (!positioned) {
      continue;
    }

    const width = getNodeWidth(positioned);
    const height = getNodeHeight(positioned);

    minX = Math.min(minX, positioned.position.x);
    minY = Math.min(minY, positioned.position.y);
    maxX = Math.max(maxX, positioned.position.x + width);
    maxY = Math.max(maxY, positioned.position.y + height);
  }

  if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
    return group;
  }

  const width = maxX - minX + GROUP_PADDING * 2;
  const height = maxY - minY + GROUP_PADDING * 2;
  const data =
    group.data && typeof group.data === 'object'
      ? (group.data as Record<string, unknown>)
      : {};

  return {
    ...group,
    position: {
      x: minX - GROUP_PADDING,
      y: minY - GROUP_PADDING,
    },
    width,
    height,
    style: {
      ...(group.style ?? {}),
      width: `${width}px`,
      height: `${height}px`,
    },
    data: {
      ...data,
      width,
      height,
    },
  };
}

function getNodeWidth(node: Node): number {
  return getDimension(
    node.width ??
      readObjectValue(node.style, 'width') ??
      readObjectValue(node.data, 'width'),
  );
}

function getNodeHeight(node: Node): number {
  return getDimension(
    node.height ??
      readObjectValue(node.style, 'height') ??
      readObjectValue(node.data, 'height'),
  );
}

function getDimension(value: unknown): number {
  if (typeof value === 'number') {
    return value;
  }

  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function readObjectValue(
  value: unknown,
  key: string,
): string | number | undefined {
  if (!value || typeof value !== 'object') {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  const candidate = record[key];

  if (typeof candidate === 'string' || typeof candidate === 'number') {
    return candidate;
  }

  return undefined;
}
