import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "reactflow";
import "reactflow/dist/style.css";
import { CANONICAL_EDGES, CANONICAL_NODES } from "@/lib/workflow/canonical-graph";
import { deriveNodeStates } from "@/lib/workflow/derive-node-state";
import type { LifecycleEventBase } from "@/types/api";
import { StageNode, type StageNodeData } from "./nodes/StageNode";

// Single memoized nodeTypes map. Passed by reference to <ReactFlow>; defining
// it at module scope avoids the React Flow re-render footgun where a fresh
// object literal triggers a full canvas remount on every parent re-render.
const NODE_TYPES = { stage: StageNode };

function projectNodes(events: LifecycleEventBase[]): Node<StageNodeData>[] {
  const states = deriveNodeStates(events);
  return CANONICAL_NODES.map((n) => ({
    ...n,
    data: { ...n.data, runtime: states[n.data.stage] },
  }));
}

function styleEdges(events: LifecycleEventBase[]): Edge[] {
  const states = deriveNodeStates(events);
  return CANONICAL_EDGES.map((e) => {
    const sourceState = states[e.source as keyof typeof states];
    const targetState = states[e.target as keyof typeof states];
    const executed =
      sourceState.state === "completed" &&
      (targetState.state === "completed" ||
        targetState.state === "blocked" ||
        targetState.state === "errored");
    return {
      ...e,
      animated: targetState.state === "active",
      style: executed
        ? { stroke: "hsl(var(--primary))", strokeWidth: 2 }
        : { stroke: "hsl(var(--muted-foreground))", strokeWidth: 1, opacity: 0.5 },
    };
  });
}

export interface LifecycleCanvasProps {
  events: LifecycleEventBase[];
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
}

export function LifecycleCanvas({ events, selectedNodeId, onNodeSelect }: LifecycleCanvasProps) {
  const nodes = useMemo(() => {
    const projected = projectNodes(events);
    if (!selectedNodeId) return projected;
    return projected.map((n) => (n.id === selectedNodeId ? { ...n, selected: true } : n));
  }, [events, selectedNodeId]);
  const edges = useMemo(() => styleEdges(events), [events]);

  const handleNodeClick = useCallback<NodeMouseHandler>(
    (_, node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect],
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  return (
    <div className="h-full w-full" style={{ minHeight: 360 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls position="bottom-right" showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
