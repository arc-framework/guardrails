import { memo, useMemo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cn } from "@/lib/utils";
import { renderCanvasText } from "@/lib/canvas/canvas-markdown";
import type { CanvasGroupNodeData, CanvasTextNodeData } from "@/lib/canvas/parse-canvas";

/**
 * Obsidian's six numbered colors mapped to ring colors that read in light
 * + dark mode. The card body stays neutral; the color shows up as a left
 * border so multiple cards stay visually separable on a dense canvas.
 */
const COLOR_BAR: Record<string, string> = {
  "1": "border-l-red-500",
  "2": "border-l-orange-500",
  "3": "border-l-yellow-500",
  "4": "border-l-green-500",
  "5": "border-l-cyan-500",
  "6": "border-l-purple-500",
};

const ACTIVE_RING = "ring-2 ring-primary ring-offset-2 ring-offset-background";

export interface CanvasTextNodeRuntime {
  active?: boolean;
  completed?: boolean;
}

/**
 * Text node. We render four invisible Handles (top/right/bottom/left) so
 * any edge from any side of the source resolves to a real attach point.
 * The handle ids match the parser's `out-<side>` / `in-<side>` convention.
 */
function CanvasTextNodeImpl(
  props: NodeProps<CanvasTextNodeData & { runtime?: CanvasTextNodeRuntime }>,
) {
  const { data } = props;
  const colorClass = data.color ? COLOR_BAR[data.color] : "border-l-border";
  const isActive = data.runtime?.active === true;
  const isCompleted = data.runtime?.completed === true;

  return (
    <div
      className={cn(
        "h-full w-full overflow-hidden rounded border border-l-4 bg-card p-3 shadow-sm transition-all",
        colorClass,
        isActive && ACTIVE_RING + " animate-pulse",
        isCompleted && "ring-1 ring-green-500/60 ring-offset-1 ring-offset-background",
      )}
    >
      {(["top", "right", "bottom", "left"] as const).map((side) => (
        <SideHandles key={side} side={side} />
      ))}
      <div className="flex flex-col gap-0.5">{renderCanvasText(data.text)}</div>
    </div>
  );
}

function SideHandles({ side }: { side: "top" | "right" | "bottom" | "left" }) {
  const position = side as Position;
  return (
    <>
      <Handle
        type="source"
        id={`out-${side}`}
        position={position}
        className="!h-1 !w-1 !border-0 !bg-transparent"
      />
      <Handle
        type="target"
        id={`in-${side}`}
        position={position}
        className="!h-1 !w-1 !border-0 !bg-transparent"
      />
    </>
  );
}

export const CanvasTextNode = memo(CanvasTextNodeImpl, (a, b) => {
  if (a.selected !== b.selected) return false;
  return (
    a.data.text === b.data.text &&
    a.data.color === b.data.color &&
    a.data.runtime?.active === b.data.runtime?.active &&
    a.data.runtime?.completed === b.data.runtime?.completed
  );
});

/**
 * Group node — a labelled translucent rectangle that visually contains
 * other nodes. Pointer-events disabled so clicks fall through to the
 * actual content nodes underneath.
 */
function CanvasGroupNodeImpl(props: NodeProps<CanvasGroupNodeData>) {
  const { data } = props;
  const colorClass = data.color ? COLOR_BAR[data.color] : "border-l-border";
  const tone = useMemo(() => toneFor(data.color), [data.color]);
  return (
    <div
      className={cn(
        "pointer-events-none h-full w-full rounded border border-l-4 border-dashed px-3 py-2",
        colorClass,
        tone,
      )}
      style={{ width: data.width, height: data.height }}
    >
      <div className="text-[11px] font-medium text-muted-foreground">{data.label}</div>
    </div>
  );
}

function toneFor(color?: string): string {
  switch (color) {
    case "1":
      return "bg-red-500/5";
    case "2":
      return "bg-orange-500/5";
    case "3":
      return "bg-yellow-500/5";
    case "4":
      return "bg-green-500/5";
    case "5":
      return "bg-cyan-500/5";
    case "6":
      return "bg-purple-500/5";
    default:
      return "bg-muted/30";
  }
}

export const CanvasGroupNode = memo(CanvasGroupNodeImpl, (a, b) => {
  return a.data.label === b.data.label && a.data.color === b.data.color;
});
