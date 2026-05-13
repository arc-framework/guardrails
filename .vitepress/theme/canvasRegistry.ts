import pipelineSwimlaneRaw from '../../docs/canvases/pipeline-swimlane.canvas?raw';
import requestDagBenignRaw from '../../docs/canvases/request-dag-benign.canvas?raw';
import requestDagBlockRaw from '../../docs/canvases/request-dag-block.canvas?raw';
import requestDagPiiRaw from '../../docs/canvases/request-dag-pii.canvas?raw';
import requestFlowTreeRaw from '../../docs/canvases/request-flow-tree.canvas?raw';
import requestFlowRaw from '../../docs/canvases/request-flow.canvas?raw';

export interface CanvasSourceNode {
  id: string;
  type: string;
  text?: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  color?: string;
  label?: string;
}

export interface CanvasSourceEdge {
  id: string;
  fromNode: string;
  fromSide?: 'left' | 'right' | 'top' | 'bottom';
  toNode: string;
  toSide?: 'left' | 'right' | 'top' | 'bottom';
  label?: string;
  animated?: boolean;
  color?: string;
}

export interface CanvasSourceDocument {
  nodes: CanvasSourceNode[];
  edges: CanvasSourceEdge[];
}

export interface CanvasEntry {
  id: string;
  title: string;
  summary: string;
  raw: string;
}

const registry: Record<string, CanvasEntry> = {
  'pipeline-swimlane': {
    id: 'pipeline-swimlane',
    title: '12-stage pipeline swimlane',
    summary:
      'Shows the shared observability lane, the main 12-stage execution path, and the plugin families attached to classification, execution, and reporting.',
    raw: pipelineSwimlaneRaw,
  },
  'request-flow-tree': {
    id: 'request-flow-tree',
    title: 'Request decision tree',
    summary:
      'Contrasts pass, redact, and block outcomes from the same classify stage so readers can see the routing split at a glance.',
    raw: requestFlowTreeRaw,
  },
  'request-flow': {
    id: 'request-flow',
    title: 'Detailed request flow',
    summary:
      'A full transport-to-response walkthrough for multiple request shapes, including service middleware, pipeline collaborators, and output handling.',
    raw: requestFlowRaw,
  },
  'request-dag-benign': {
    id: 'request-dag-benign',
    title: 'Benign request event DAG',
    summary:
      'Visualizes the lifecycle event structure for a clean request path where the backend is called and the pipeline completes without intervention.',
    raw: requestDagBenignRaw,
  },
  'request-dag-pii': {
    id: 'request-dag-pii',
    title: 'PII redaction event DAG',
    summary:
      'Highlights the finding, placeholder map, strategy execution, and decision emission path for a redaction-focused request.',
    raw: requestDagPiiRaw,
  },
  'request-dag-block': {
    id: 'request-dag-block',
    title: 'Blocked request event DAG',
    summary:
      'Shows the early-exit lifecycle path for critical prompt injection or jailbreak findings that never reach the backend.',
    raw: requestDagBlockRaw,
  },
};

const parsedCache = new Map<string, CanvasSourceDocument>();

export function listCanvasEntries(): CanvasEntry[] {
  return Object.values(registry);
}

export function getCanvasEntry(id: string): CanvasEntry | null {
  return registry[id] ?? null;
}

export function getCanvasDocument(id: string): CanvasSourceDocument | null {
  if (!registry[id]) {
    return null;
  }
  if (!parsedCache.has(id)) {
    parsedCache.set(id, JSON.parse(registry[id].raw) as CanvasSourceDocument);
  }
  return parsedCache.get(id) ?? null;
}
