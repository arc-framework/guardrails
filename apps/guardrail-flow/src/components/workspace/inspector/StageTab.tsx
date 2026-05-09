import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { JsonView } from "@/components/shared/JsonView";
import type { LifecycleEventBase, StageName } from "@/types/api";
import type { WorkflowNodeState } from "@/types/workflow";

export interface StageTabProps {
  selectedNode: WorkflowNodeState | null;
  events: LifecycleEventBase[];
}

export function StageTab({ selectedNode, events }: StageTabProps) {
  if (!selectedNode) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        Select a stage on the canvas to inspect its events and metadata.
      </p>
    );
  }

  const scoped = filterToStage(events, selectedNode.stage);

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-1 px-1">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{selectedNode.stage}</span>
          <Badge variant={badgeVariantFor(selectedNode.state)}>{selectedNode.state}</Badge>
        </div>
        <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
          <span>duration</span>
          <span className="text-right">
            {selectedNode.durationMs !== null ? `${selectedNode.durationMs} ms` : "—"}
          </span>
          <span>findings</span>
          <span className="text-right">{selectedNode.findingCount}</span>
          {selectedNode.jailbreakHit ? (
            <>
              <span>jailbreak</span>
              <span className="text-right">hit</span>
            </>
          ) : null}
          {selectedNode.deceptionScore !== null ? (
            <>
              <span>deception</span>
              <span className="text-right">{selectedNode.deceptionScore.toFixed(2)}</span>
            </>
          ) : null}
        </div>
      </header>
      <Separator />
      <div className="flex flex-col gap-2 px-1">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Events ({scoped.length})
        </h3>
        {scoped.length === 0 ? (
          <p className="text-xs text-muted-foreground">No events recorded for this stage.</p>
        ) : (
          <ul className="space-y-2">
            {scoped.map((event) => (
              <li key={event.id} className="rounded border bg-background">
                <div className="flex items-center justify-between p-2 text-xs">
                  <span className="font-mono">{event.event_type}</span>
                  <span className="text-muted-foreground">seq {event.seq}</span>
                </div>
                <Separator />
                <div className="p-1">
                  <JsonView value={event} maxHeight="200px" />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function filterToStage(events: LifecycleEventBase[], stage: StageName): LifecycleEventBase[] {
  return events.filter((e) => {
    const evStage = (e as Record<string, unknown>).stage;
    return typeof evStage === "string" && evStage === stage;
  });
}

function badgeVariantFor(
  state: WorkflowNodeState["state"],
): "default" | "secondary" | "outline" | "destructive" {
  switch (state) {
    case "completed":
      return "default";
    case "active":
      return "secondary";
    case "blocked":
    case "errored":
      return "destructive";
    default:
      return "outline";
  }
}
