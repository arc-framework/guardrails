import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CANONICAL_EDGES, CANONICAL_NODES } from "@/lib/workflow/canonical-graph";
import { deriveNodeStates } from "@/lib/workflow/derive-node-state";
import { spreadLayout } from "@/lib/canvas/dagre-layout";
import { usePathPlayback } from "@/hooks/usePathPlayback";
import { useUiStore, type CanvasSpreadLevel } from "@/lib/state/ui-store";
import type { LifecycleEventBase, StageName } from "@/types/api";
import { StageNode, type StageNodeData } from "./nodes/StageNode";

// Single memoized nodeTypes map. Passed by reference to <ReactFlow>; defining
// it at module scope avoids the React Flow re-render footgun where a fresh
// object literal literal triggers a full canvas remount on every parent
// re-render.
const NODE_TYPES = { stage: StageNode };

// Per FR-031e: level 1 default ("Spread"), level 2 comfortable ("Wide"),
// level 3 wide ("Reset"). Cycling repeats from level 1.
const SPREAD_FACTOR_BY_LEVEL: Record<CanvasSpreadLevel, number> = {
  1: 1.05,
  2: 1.5,
  3: 2.2,
};

const SPREAD_LABEL_BY_LEVEL: Record<CanvasSpreadLevel, string> = {
  1: "Spread",
  2: "Wide",
  3: "Reset",
};

function projectNodes(
  events: LifecycleEventBase[],
  activeOverride: StageName | null,
): Node<StageNodeData>[] {
  const states = deriveNodeStates(events, activeOverride);
  return CANONICAL_NODES.map((n) => ({
    ...n,
    data: { ...n.data, runtime: states[n.data.stage] },
  }));
}

function styleEdges(events: LifecycleEventBase[], activeOverride: StageName | null): Edge[] {
  const states = deriveNodeStates(events, activeOverride);
  return CANONICAL_EDGES.map((e) => {
    const sourceState = states[e.source as keyof typeof states];
    const targetState = states[e.target as keyof typeof states];
    const executed =
      sourceState.state === "completed" &&
      (targetState.state === "completed" ||
        targetState.state === "blocked" ||
        targetState.state === "errored");
    const leadingActive = sourceState.state === "completed" && targetState.state === "active";
    // Animate flowing dashes on every edge that's part of the executed
    // path PLUS the leading edge into the currently-active stage. Idle
    // edges stay still so the eye isn't drawn to them.
    const animated = executed || leadingActive;
    const stroke =
      executed || leadingActive ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))";
    return {
      ...e,
      animated,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 14,
        height: 14,
        color: stroke,
      },
      style:
        executed || leadingActive
          ? { stroke, strokeWidth: 2 }
          : { stroke, strokeWidth: 1, opacity: 0.5 },
    };
  });
}

/**
 * Build the playback path: the unique sequence of stages the request
 * actually traversed, in chronological order. We restrict to `StageRan`
 * events so the playback skips intra-stage detail (FindingProduced /
 * DeceptionScored / etc.) and steps from one stage card to the next.
 */
function buildStagePath(events: LifecycleEventBase[]): StageName[] {
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  const path: StageName[] = [];
  for (const ev of ordered) {
    if (ev.event_type !== "StageRan") continue;
    const stage = (ev as { stage?: StageName }).stage;
    if (!stage) continue;
    if (path[path.length - 1] !== stage) {
      path.push(stage);
    }
  }
  return path;
}

/**
 * During playback, expose only events up to the current playback step.
 * StageRan events for stages BEYOND the current playhead are filtered out
 * so the canvas state matches the playback cursor. Non-stage events
 * (FindingProduced etc.) attached to already-played stages are kept.
 */
function eventsUpTo(
  events: LifecycleEventBase[],
  stagesPlayed: ReadonlySet<string>,
): LifecycleEventBase[] {
  // Find the seq of the last-played stage's StageRan event so we can keep
  // only events at-or-before that point in time.
  let cutoffSeq = -1;
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  for (const ev of ordered) {
    if (ev.event_type !== "StageRan") continue;
    const stage = (ev as { stage?: string }).stage;
    if (stage && stagesPlayed.has(stage)) {
      cutoffSeq = Math.max(cutoffSeq, ev.seq);
    }
  }
  if (cutoffSeq < 0) return [];
  return ordered.filter((e) => e.seq <= cutoffSeq);
}

export interface LifecycleCanvasProps {
  events: LifecycleEventBase[];
  activeStage?: StageName | null;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
}

export function LifecycleCanvas({
  events,
  activeStage = null,
  selectedNodeId,
  onNodeSelect,
}: LifecycleCanvasProps) {
  const spreadLevel = useUiStore((s) => s.canvasSpreadLevel);
  const cycleSpread = useUiStore((s) => s.cycleCanvasSpreadLevel);

  const stagePath = useMemo(() => buildStagePath(events), [events]);
  const playback = usePathPlayback({ path: stagePath, stepMs: 350 });

  // Effective events: the full set when not playing, sliced to the
  // playback cursor when playing.
  const effectiveEvents = useMemo(() => {
    if (playback.status === "idle" || playback.currentIndex < 0) return events;
    return eventsUpTo(events, playback.visited);
  }, [events, playback.status, playback.currentIndex, playback.visited]);

  // The replay cursor only paints a stage as ``active`` while playback is
  // live. ``complete`` returns the canvas to its natural terminal state.
  const replayActive = useMemo<StageName | null>(() => {
    if (playback.status !== "playing" && playback.status !== "paused") return null;
    return (playback.currentId as StageName | null) ?? null;
  }, [playback.status, playback.currentId]);

  const effectiveActiveStage = replayActive ?? activeStage;

  const baseNodes = useMemo(() => {
    const projected = projectNodes(effectiveEvents, effectiveActiveStage);
    if (!selectedNodeId) return projected;
    return projected.map((n) => (n.id === selectedNodeId ? { ...n, selected: true } : n));
  }, [effectiveEvents, effectiveActiveStage, selectedNodeId]);

  const baseEdges = useMemo(
    () => styleEdges(effectiveEvents, effectiveActiveStage),
    [effectiveEvents, effectiveActiveStage],
  );

  const spread = useMemo(
    () => spreadLayout(baseNodes, baseEdges, SPREAD_FACTOR_BY_LEVEL[spreadLevel]),
    [baseNodes, baseEdges, spreadLevel],
  );

  const nodes = spread.nodes;
  const edges = spread.edges;

  const handleNodeClick = useCallback<NodeMouseHandler>(
    (_, node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect],
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  const showPlay = playback.status === "idle";
  const showPause = playback.status === "playing";
  const showResume = playback.status === "paused";
  const playbackEnabled = stagePath.length > 0;

  return (
    <div className="relative h-full w-full" style={{ minHeight: 360 }}>
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

      <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-md border bg-card/95 px-2 py-1 shadow-sm backdrop-blur">
        <Button
          variant={spreadLevel === 1 ? "outline" : "default"}
          size="sm"
          onClick={cycleSpread}
          aria-label={`Spread level ${spreadLevel} of 3 — click to cycle`}
          title={`Layout density level ${spreadLevel}/3. Click to cycle Spread → Wide → Reset.`}
        >
          {SPREAD_LABEL_BY_LEVEL[spreadLevel]}
        </Button>

        {playbackEnabled ? (
          <>
            <Separator orientation="vertical" className="h-5" />
            {showPlay ? (
              <Button
                variant="default"
                size="sm"
                onClick={playback.play}
                title="Replay this request stage-by-stage"
              >
                ▶ Replay
              </Button>
            ) : null}
            {showPause ? (
              <Button variant="outline" size="sm" onClick={playback.pause} title="Pause">
                ❚❚
              </Button>
            ) : null}
            {showResume ? (
              <Button variant="default" size="sm" onClick={playback.resume} title="Resume">
                ▶
              </Button>
            ) : null}
            {playback.status !== "idle" ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={playback.skipToEnd}
                  title="Jump to final state"
                >
                  ⏭
                </Button>
                <Button variant="ghost" size="sm" onClick={playback.reset} title="Reset to start">
                  ↺
                </Button>
              </>
            ) : null}
            <Badge variant="outline" className="text-[10px]">
              {playback.currentIndex + 1} / {stagePath.length}
            </Badge>
          </>
        ) : null}
      </div>
    </div>
  );
}
