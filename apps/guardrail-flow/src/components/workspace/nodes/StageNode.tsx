import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CanonicalNodeData } from "@/lib/workflow/canonical-graph";
import type { WorkflowNodeState } from "@/types/workflow";

export type StageNodeData = CanonicalNodeData & {
  runtime: WorkflowNodeState;
};

const STATE_STYLES: Record<WorkflowNodeState["state"], string> = {
  inactive: "border-border bg-card text-muted-foreground opacity-50",
  active: "border-primary bg-primary/10 text-foreground animate-pulse",
  completed: "border-green-500/60 bg-green-500/10 text-foreground",
  skipped: "border-dashed border-muted-foreground/40 bg-muted/30 text-muted-foreground",
  blocked: "border-destructive bg-destructive/15 text-foreground",
  errored: "border-destructive bg-destructive/5 text-destructive",
};

function StageBadges({ rt }: { rt: WorkflowNodeState }) {
  const items: { label: string; tone: "default" | "secondary" | "destructive" | "outline" }[] = [];
  if (rt.findingCount > 0) items.push({ label: `${rt.findingCount} findings`, tone: "secondary" });
  if (rt.jailbreakHit) items.push({ label: "jailbreak", tone: "destructive" });
  if (rt.deceptionScore !== null)
    items.push({
      label: `deception ${rt.deceptionScore.toFixed(2)}`,
      tone: "secondary",
    });
  if (rt.durationMs !== null && rt.state !== "inactive")
    items.push({ label: `${Math.round(rt.durationMs)}ms`, tone: "outline" });
  if (items.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {items.map((it) => (
        <Badge key={it.label} variant={it.tone} className="text-[10px]">
          {it.label}
        </Badge>
      ))}
    </div>
  );
}

function StageNodeImpl({ data, selected }: NodeProps<StageNodeData>) {
  const { runtime } = data;
  return (
    <div
      className={cn(
        "min-w-[140px] rounded-md border-2 px-3 py-2 transition-colors",
        STATE_STYLES[runtime.state],
        selected ? "ring-2 ring-ring ring-offset-2" : "",
      )}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <div className="text-sm font-semibold">{data.label}</div>
      <div className="text-[10px] text-muted-foreground">{data.description}</div>
      <StageBadges rt={runtime} />
      <Handle type="source" position={Position.Right} className="opacity-0" />
    </div>
  );
}

export const StageNode = memo(StageNodeImpl, (prev, next) => {
  // Re-render only when our slice of state actually changes.
  if (prev.selected !== next.selected) return false;
  const a = prev.data.runtime;
  const b = next.data.runtime;
  return (
    a.state === b.state &&
    a.durationMs === b.durationMs &&
    a.findingCount === b.findingCount &&
    a.jailbreakHit === b.jailbreakHit &&
    a.deceptionScore === b.deceptionScore
  );
});
