import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { JsonView } from "@/components/shared/JsonView";
import { useUiStore } from "@/lib/state/ui-store";
import { maskPayload } from "@/lib/privacy/mask";
import type { LifecycleEventBase, StageName } from "@/types/api";
import type { WorkflowNodeState } from "@/types/workflow";

export interface StageTabProps {
  selectedNode: WorkflowNodeState | null;
  events: LifecycleEventBase[];
}

interface TextDelta {
  source: string;
  before: string;
  after: string;
}

/** Maps a text-bearing event type to the canvas stage it belongs to in the
 *  operator's mental model. Used to scope the "Text deltas" panel to the
 *  currently-selected stage. */
const TEXT_BEARING_TO_STAGE: Record<string, StageName> = {
  SanitizationApplied: "sanitize",
  StrategyExecuted: "execute",
  PayloadRewritten: "execute",
  RehydrationVerified: "rehydrate",
};

export function StageTab({ selectedNode, events }: StageTabProps) {
  const masked = useUiStore((s) => s.payloadVisibility === "masked");
  if (!selectedNode) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        Select a stage on the canvas to inspect its events and metadata.
      </p>
    );
  }

  const scoped = filterToStage(events, selectedNode.stage);
  const textDeltas = extractTextDeltasForStage(events, selectedNode.stage);

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
      {textDeltas.length > 0 ? (
        <>
          <Separator />
          <div className="flex flex-col gap-2 px-1">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Text deltas ({textDeltas.length})
            </h3>
            {textDeltas.map((delta, idx) => (
              <details key={`${delta.source}-${idx}`} className="rounded border bg-background">
                <summary className="cursor-pointer px-2 py-1 text-[11px] font-mono">
                  {delta.source}
                </summary>
                <div className="space-y-1 border-t p-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    before
                  </p>
                  <pre className="max-h-[280px] min-h-[120px] overflow-auto whitespace-pre-wrap break-words rounded border bg-muted/30 p-2 text-[11px] leading-snug">
                    {masked ? maskPayload(delta.before) : delta.before}
                  </pre>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    after
                  </p>
                  <pre className="max-h-[280px] min-h-[120px] overflow-auto whitespace-pre-wrap break-words rounded border bg-muted/30 p-2 text-[11px] leading-snug">
                    {masked ? maskPayload(delta.after) : delta.after}
                  </pre>
                </div>
              </details>
            ))}
          </div>
        </>
      ) : null}
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

function extractTextDeltasForStage(
  events: LifecycleEventBase[],
  stage: StageName,
): TextDelta[] {
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  const out: TextDelta[] = [];
  for (const e of ordered) {
    const mappedStage = TEXT_BEARING_TO_STAGE[e.event_type];
    if (mappedStage !== stage) continue;
    const r = e as Record<string, unknown>;
    if (typeof r.text_before === "string" && typeof r.text_after === "string") {
      out.push({
        source: `${e.event_type}.text_before / text_after`,
        before: r.text_before,
        after: r.text_after,
      });
    }
  }
  return out;
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
