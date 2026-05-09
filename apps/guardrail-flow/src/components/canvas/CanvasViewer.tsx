import { useCallback, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, MarkerType, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CanvasGroupNode, CanvasTextNode } from "./CanvasNodes";
import { spreadLayout } from "@/lib/canvas/dagre-layout";
import { usePathPlayback } from "@/hooks/usePathPlayback";

const NODE_TYPES = {
  canvasText: CanvasTextNode,
  canvasGroup: CanvasGroupNode,
};

export interface CanvasViewerProps {
  /** Initial nodes from `parseCanvas`. */
  nodes: Node[];
  /** Initial edges from `parseCanvas`. */
  edges: Edge[];
  /**
   * Optional ordered path of node ids to highlight in sequence when "Play"
   * is pressed. Pass an empty array to hide playback controls.
   */
  playbackPath?: string[];
  /**
   * Optional label for the Play button, e.g. "Replay request 01JFIXT0RID01".
   */
  playbackLabel?: string;
  /** Optional override step delay (ms). Default 400. */
  stepMs?: number;
  /**
   * Show or hide the bottom-right toolbar; pass `false` for read-only embeds.
   * Default true.
   */
  showToolbar?: boolean;
}

type LayoutMode = "original" | "spread";

export function CanvasViewer({
  nodes: initialNodes,
  edges: initialEdges,
  playbackPath = [],
  playbackLabel,
  stepMs = 400,
  showToolbar = true,
}: CanvasViewerProps) {
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("original");

  // Memoize the spread layout so it's computed once per node-set; flipping
  // back to original is free.
  const spread = useMemo(
    () => spreadLayout(initialNodes, initialEdges),
    [initialNodes, initialEdges],
  );

  const playback = usePathPlayback({ path: playbackPath, stepMs });

  // Decorate nodes with runtime state from the playback hook so the active
  // node animates and visited nodes stay highlighted.
  const decoratedNodes = useMemo(() => {
    const source = layoutMode === "spread" ? spread.nodes : initialNodes;
    if (playback.currentIndex < 0) return source;
    return source.map((n) => {
      if (n.type !== "canvasText") return n;
      const isCurrent = n.id === playback.currentId;
      const isVisited = playback.visited.has(n.id) && !isCurrent;
      return {
        ...n,
        data: {
          ...n.data,
          runtime: { active: isCurrent, completed: isVisited },
        },
      };
    });
  }, [
    layoutMode,
    spread.nodes,
    initialNodes,
    playback.currentId,
    playback.currentIndex,
    playback.visited,
  ]);

  const decoratedEdges = useMemo(() => {
    const baseStroke = "hsl(var(--muted-foreground))";
    const activeStroke = "hsl(var(--primary))";

    // Without playback running, every edge gets a static arrow — the
    // canvas already shows direction but explicit arrowheads sharpen
    // the read on dense diagrams.
    if (playback.currentIndex < 0) {
      return initialEdges.map((e) => ({
        ...e,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: baseStroke,
        },
      }));
    }

    const visited = playback.visited;
    return initialEdges.map((e) => {
      const onPath = visited.has(e.source) && visited.has(e.target);
      const isLeading = playback.currentId !== null && e.source === playback.currentId;
      const stroke = onPath || isLeading ? activeStroke : baseStroke;
      return {
        ...e,
        animated: onPath || isLeading,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: stroke,
        },
        style: onPath
          ? { stroke, strokeWidth: 2 }
          : isLeading
            ? { stroke, strokeWidth: 1.5, strokeDasharray: "6 4" }
            : { stroke, strokeWidth: 1, opacity: 0.5 },
      };
    });
  }, [initialEdges, playback.currentId, playback.currentIndex, playback.visited]);

  const toggleLayout = useCallback(() => {
    setLayoutMode((m) => (m === "original" ? "spread" : "original"));
  }, []);

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={decoratedNodes}
        edges={decoratedEdges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls position="bottom-right" showInteractive={false} />
      </ReactFlow>

      {showToolbar ? (
        <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-md border bg-card/95 px-2 py-1 shadow-sm backdrop-blur">
          <Button
            variant={layoutMode === "spread" ? "default" : "outline"}
            size="sm"
            onClick={toggleLayout}
            aria-pressed={layoutMode === "spread"}
            title={
              layoutMode === "spread"
                ? "Return to the hand-tuned canvas layout"
                : "Spread nodes outward for breathing room (preserves orientation)"
            }
          >
            {layoutMode === "spread" ? "Original" : "Spread"}
          </Button>

          {playbackPath.length > 0 ? (
            <>
              <Separator orientation="vertical" className="h-5" />
              <PlaybackControls
                playback={playback}
                pathLength={playbackPath.length}
                playbackLabel={playbackLabel}
              />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PlaybackControls({
  playback,
  pathLength,
  playbackLabel,
}: {
  playback: ReturnType<typeof usePathPlayback>;
  pathLength: number;
  playbackLabel?: string;
}) {
  const { status, currentIndex, play, pause, resume, skipToEnd, reset } = playback;

  const showPlay = status === "idle";
  const showPause = status === "playing";
  const showResume = status === "paused";

  return (
    <div className="flex items-center gap-1.5">
      {showPlay ? (
        <Button variant="default" size="sm" onClick={play} title={playbackLabel ?? "Play"}>
          ▶ Play
        </Button>
      ) : null}
      {showPause ? (
        <Button variant="outline" size="sm" onClick={pause} title="Pause">
          ❚❚
        </Button>
      ) : null}
      {showResume ? (
        <Button variant="default" size="sm" onClick={resume} title="Resume">
          ▶
        </Button>
      ) : null}
      {status !== "idle" ? (
        <>
          <Button variant="ghost" size="sm" onClick={skipToEnd} title="Skip to end">
            ⏭
          </Button>
          <Button variant="ghost" size="sm" onClick={reset} title="Reset">
            ↺
          </Button>
        </>
      ) : null}
      {currentIndex >= 0 ? (
        <Badge variant="outline" className="text-[10px]">
          {currentIndex + 1} / {pathLength}
        </Badge>
      ) : (
        <span className="text-[10px] text-muted-foreground">{pathLength} steps</span>
      )}
    </div>
  );
}
