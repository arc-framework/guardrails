import { MarkerType, type Edge, type Node } from '@vue-flow/core';
import { fitGroupBounds } from './canvasLayout';
import type {
  CanvasSourceDocument,
  CanvasSourceEdge,
  CanvasSourceNode,
} from './canvasRegistry';

export interface CanvasTextNodeData {
  text: string;
  color?: string;
  compact?: boolean;
  heading?: boolean;
}

export interface CanvasGroupNodeData {
  label: string;
  color?: string;
  width: number;
  height: number;
}

export interface ParsedCanvas {
  nodes: Node[];
  edges: Edge[];
}

const EDGE_STROKE: Record<string, string> = {
  '0': 'rgba(100, 116, 139, 0.72)',
  '1': 'rgba(239, 68, 68, 0.78)',
  '2': 'rgba(249, 115, 22, 0.78)',
  '3': 'rgba(234, 179, 8, 0.78)',
  '4': 'rgba(34, 197, 94, 0.78)',
  '5': 'rgba(6, 182, 212, 0.78)',
  '6': 'rgba(168, 85, 247, 0.78)',
};

const MIN_TEXT_WIDTH = 268;
const MAX_TEXT_WIDTH = 420;
const MIN_TEXT_HEIGHT = 112;
const WIDTH_STEP = 28;
const HEIGHT_STEP = 20;
const CONTENT_PADDING_Y = 24;
const CONTENT_PADDING_X = 24;
const CHAR_PIXEL_WIDTH = 7.2;
const BASE_LINE_HEIGHT = 20;
const H1_LINE_HEIGHT = 28;
const H2_LINE_HEIGHT = 25;
const H3_LINE_HEIGHT = 22;
const BLANK_LINE_HEIGHT = 12;
const BULLET_INDENT_CHARS = 3;

export function parseCanvas(document: CanvasSourceDocument): ParsedCanvas {
  const groupNodes: Node<CanvasGroupNodeData>[] = document.nodes
    .filter((node): node is CanvasSourceNode => node.type === 'group')
    .map((node) => {
      const width = node.width ?? 0;
      const height = node.height ?? 0;

      return {
        id: node.id,
        type: 'canvasGroup',
        position: { x: node.x, y: node.y },
        width,
        height,
        style: {
          width: `${width}px`,
          height: `${height}px`,
        },
        data: {
          label: node.label ?? 'Group',
          color: node.color,
          width,
          height,
        },
        draggable: false,
        selectable: false,
        focusable: false,
        zIndex: -1,
      };
    });

  const textNodes: Node<CanvasTextNodeData>[] = document.nodes
    .filter((node): node is CanvasSourceNode => node.type === 'text')
    .map((node) => {
      const size = estimateTextNodeSize(
        node.text ?? '',
        node.width,
        node.height,
      );
      const width = size.width;
      const height = size.height;

      return {
        id: node.id,
        type: 'canvasText',
        position: { x: node.x, y: node.y },
        width,
        height,
        style: {
          width: `${width}px`,
          height: `${height}px`,
        },
        data: {
          text: node.text ?? '',
          color: node.color,
          compact: isCompactTextNode(node.text ?? '', height),
          heading: isHeadingTextNode(node.text ?? ''),
        },
        draggable: false,
        connectable: false,
        selectable: true,
        focusable: true,
        zIndex: 1,
      };
    });

  const edges: Edge[] = document.edges.map((edge) => mapEdge(edge));
  const nodes = fitGroupBounds([...groupNodes, ...textNodes]);

  return {
    nodes,
    edges,
  };
}

function mapEdge(edge: CanvasSourceEdge): Edge {
  const stroke = edgeStroke(edge.color);

  return {
    id: edge.id,
    source: edge.fromNode,
    target: edge.toNode,
    sourceHandle: edge.fromSide ? `out-${edge.fromSide}` : undefined,
    targetHandle: edge.toSide ? `in-${edge.toSide}` : undefined,
    type: 'smoothstep',
    label: edge.label,
    animated: Boolean(edge.animated),
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 14,
      height: 14,
      color: stroke,
    },
    style: {
      stroke,
      strokeWidth: edge.animated ? 1.8 : 1.15,
      opacity: edge.animated ? 1 : 0.72,
    },
    labelStyle: {
      fill: 'var(--vp-c-text-2)',
      fontSize: '11px',
      fontWeight: 600,
    },
    labelBgPadding: [4, 6],
    labelBgBorderRadius: 8,
  };
}

function edgeStroke(color?: string): string {
  return EDGE_STROKE[color ?? '0'] ?? EDGE_STROKE['0'];
}

function estimateTextNodeSize(
  text: string,
  sourceWidth?: number,
  sourceHeight?: number,
): { width: number; height: number } {
  const lines = normalizeLines(text);
  const hasSourceWidth = typeof sourceWidth === 'number' && sourceWidth > 0;
  const hasSourceHeight = typeof sourceHeight === 'number' && sourceHeight > 0;
  const preferredWidth = estimatePreferredWidth(lines);
  const fallbackWidth = roundUpToStep(
    Math.min(Math.max(preferredWidth, MIN_TEXT_WIDTH), MAX_TEXT_WIDTH),
    WIDTH_STEP,
  );
  const width = hasSourceWidth ? sourceWidth : fallbackWidth;
  const availableTextWidth = Math.max(width - CONTENT_PADDING_X * 2, 180);
  const heightEstimate = estimateHeight(lines, availableTextWidth);
  const fallbackHeight = roundUpToStep(
    Math.max(heightEstimate, MIN_TEXT_HEIGHT),
    HEIGHT_STEP,
  );
  const height = hasSourceHeight ? sourceHeight : fallbackHeight;

  return { width, height };
}

function isCompactTextNode(text: string, height: number): boolean {
  const nonBlankLines = normalizeLines(text).filter(
    (line) => line.trim() !== '',
  );

  if (height > 0 && height <= 64) {
    return true;
  }

  return (
    isHeadingTextNode(text) &&
    height > 0 &&
    height <= 132 &&
    nonBlankLines.length <= 3
  );
}

function isHeadingTextNode(text: string): boolean {
  const firstLine = normalizeLines(text)
    .map((line) => line.trim())
    .find(Boolean);

  return (
    typeof firstLine === 'string' &&
    /^(#{1,3}\s|[A-Z]{2,}\d*\b|UC\d\s·)/.test(firstLine)
  );
}

function normalizeLines(text: string): string[] {
  const lines = text.split('\n').map((line) => line.replace(/\s+$/g, ''));

  return lines.length > 0 ? lines : [''];
}

function estimatePreferredWidth(lines: string[]): number {
  let widest = 0;

  for (const line of lines) {
    const content = effectiveLineText(line);
    widest = Math.max(widest, content.length);
  }

  return Math.ceil(widest * CHAR_PIXEL_WIDTH + CONTENT_PADDING_X * 2);
}

function estimateHeight(lines: string[], availableTextWidth: number): number {
  let height = CONTENT_PADDING_Y * 2;

  for (const line of lines) {
    const kind = classifyLine(line);
    const content = effectiveLineText(line);

    if (kind === 'blank') {
      height += BLANK_LINE_HEIGHT;
      continue;
    }

    const charWidth =
      kind === 'body' || kind === 'bullet'
        ? CHAR_PIXEL_WIDTH
        : CHAR_PIXEL_WIDTH + 0.2;
    const charsPerLine = Math.max(
      10,
      Math.floor(availableTextWidth / charWidth),
    );
    const logicalLength = Math.max(
      1,
      content.length + (kind === 'bullet' ? BULLET_INDENT_CHARS : 0),
    );
    const wraps = Math.max(1, Math.ceil(logicalLength / charsPerLine));
    height += wraps * lineHeightFor(kind);
  }

  return height;
}

function classifyLine(
  line: string,
): 'h1' | 'h2' | 'h3' | 'bullet' | 'body' | 'blank' {
  const trimmed = line.trim();

  if (trimmed === '') {
    return 'blank';
  }

  if (trimmed.startsWith('### ')) {
    return 'h3';
  }

  if (trimmed.startsWith('## ')) {
    return 'h2';
  }

  if (trimmed.startsWith('# ')) {
    return 'h1';
  }

  if (trimmed.startsWith('- ')) {
    return 'bullet';
  }

  return 'body';
}

function effectiveLineText(line: string): string {
  return line
    .trim()
    .replace(/^#{1,3}\s+/, '')
    .replace(/^-\s+/, '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\*/g, '');
}

function lineHeightFor(
  kind: 'h1' | 'h2' | 'h3' | 'bullet' | 'body' | 'blank',
): number {
  switch (kind) {
    case 'h1':
      return H1_LINE_HEIGHT;
    case 'h2':
      return H2_LINE_HEIGHT;
    case 'h3':
      return H3_LINE_HEIGHT;
    case 'blank':
      return BLANK_LINE_HEIGHT;
    default:
      return BASE_LINE_HEIGHT;
  }
}

function roundUpToStep(value: number, step: number): number {
  return Math.ceil(value / step) * step;
}
