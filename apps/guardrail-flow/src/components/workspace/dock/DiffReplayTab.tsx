import { useMemo } from "react";
import { EmptyState } from "@/components/shared/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { tokenDiff, type DiffOp } from "@/lib/diff/token-diff";
import { useUiStore } from "@/lib/state/ui-store";
import { maskPayload } from "@/lib/privacy/mask";
import { cn } from "@/lib/utils";
import type { LifecycleEventBase } from "@/types/api";

export interface DiffReplayTabProps {
  events: LifecycleEventBase[];
}

interface DiffPanel {
  source: string;
  label: string;
  before: string;
  after: string;
}

const DIFF_BEARING_EVENTS: ReadonlyArray<{
  event_type: string;
  label: string;
}> = [
  { event_type: "SanitizationApplied", label: "sanitize" },
  { event_type: "StrategyExecuted", label: "execute" },
  { event_type: "PayloadRewritten", label: "payload-rewrite" },
  { event_type: "RehydrationVerified", label: "rehydrate" },
];

export function DiffReplayTab({ events }: DiffReplayTabProps) {
  const masked = useUiStore((s) => s.payloadVisibility === "masked");
  const panels = useMemo(() => extractPanels(events), [events]);

  if (panels.length === 0) {
    return (
      <EmptyState
        title="No diffs to render"
        description="Diff/Replay needs both text_before and text_after on a transformative stage. Capture flags are off by default — set ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_PAYLOADS=true on the api side to populate them."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3 px-1 py-2">
      {panels.map((panel, idx) => (
        <section key={`${panel.source}-${idx}`} className="rounded border bg-background p-2">
          <header className="mb-2 flex items-center gap-2 text-[11px]">
            <Badge variant="secondary" className="uppercase">
              {panel.label}
            </Badge>
            <span className="font-mono text-muted-foreground">{panel.source}</span>
          </header>
          {masked ? (
            <p className="text-[11px] text-muted-foreground">
              {maskPayload(panel.before)} → {maskPayload(panel.after)}
            </p>
          ) : (
            <DiffView ops={tokenDiff(panel.before, panel.after)} />
          )}
          {idx < panels.length - 1 ? <Separator className="mt-2" /> : null}
        </section>
      ))}
    </div>
  );
}

function DiffView({ ops }: { ops: DiffOp[] }) {
  return (
    <pre className="max-h-[280px] overflow-auto whitespace-pre-wrap break-words text-[11px] leading-snug">
      {ops.map((op, idx) => (
        <span
          key={idx}
          className={cn(
            op.kind === "remove" && "rounded bg-red-100/60 text-red-900 line-through dark:bg-red-900/30 dark:text-red-100",
            op.kind === "add" && "rounded bg-emerald-100/60 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-100",
          )}
        >
          {op.text}
        </span>
      ))}
    </pre>
  );
}

function extractPanels(events: LifecycleEventBase[]): DiffPanel[] {
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  const panels: DiffPanel[] = [];
  for (const e of ordered) {
    const config = DIFF_BEARING_EVENTS.find((c) => c.event_type === e.event_type);
    if (!config) continue;
    const r = e as Record<string, unknown>;
    const before = stringOrNull(r.text_before);
    const after = stringOrNull(r.text_after);
    if (before === null || after === null) continue;
    panels.push({
      source: `${e.event_type}.text_before / text_after`,
      label: config.label,
      before,
      after,
    });
  }
  return panels;
}

function stringOrNull(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}
