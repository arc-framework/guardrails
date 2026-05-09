import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { LifecycleEventBase } from "@/types/api";

export interface PayloadTabProps {
  events: LifecycleEventBase[];
}

interface PayloadField {
  label: string;
  source: string;
  value: string | null;
  /** Some events don't appear at all (e.g. no backend call) — distinct from "captured but null". */
  eventPresent: boolean;
}

export function PayloadTab({ events }: PayloadTabProps) {
  const fields = extractPayloadFields(events);
  const anyCaptured = fields.some((f) => f.value !== null);

  return (
    <div className="flex flex-col gap-3 px-1">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Captured user-facing payloads. Off by default — backend operator opts in via{" "}
          <code className="rounded bg-muted px-1 text-[10px]">
            ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_RAW_INPUT
          </code>{" "}
          and{" "}
          <code className="rounded bg-muted px-1 text-[10px]">
            ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_PAYLOADS
          </code>
          .
        </p>
        <Badge variant={anyCaptured ? "default" : "outline"}>
          {anyCaptured ? "capture: on" : "capture: off"}
        </Badge>
      </div>

      {!anyCaptured ? (
        <div className="rounded border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
          No payloads captured for this request. Either capture is disabled at the backend or this
          path of the lifecycle did not produce any payload-bearing events. Lifecycle metadata,
          findings, and decisions are still visible on the other tabs.
        </div>
      ) : null}

      <Separator />

      <ul className="flex flex-col gap-3">
        {fields.map((f) => (
          <li key={`${f.source}.${f.label}`} className="flex flex-col gap-1">
            <header className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold">{f.label}</span>
                <span className="text-[10px] text-muted-foreground">{f.source}</span>
              </div>
              <Badge variant={badgeVariant(f)}>{statusFor(f)}</Badge>
            </header>
            {f.value !== null ? (
              <pre className="max-h-[280px] min-h-[120px] overflow-auto whitespace-pre-wrap break-words rounded border bg-background p-2 text-[11px] leading-snug">
                {f.value}
              </pre>
            ) : (
              <div className="rounded border border-dashed bg-muted/30 p-2 text-[11px] text-muted-foreground">
                {statusDetail(f)}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function extractPayloadFields(events: LifecycleEventBase[]): PayloadField[] {
  const requestStarted = events.find((e) => e.event_type === "RequestStarted");
  const backendResponded = events.find((e) => e.event_type === "BackendResponded");

  return [
    {
      label: "Original input",
      source: "RequestStarted.raw_input",
      value: stringOrNull((requestStarted as Record<string, unknown> | undefined)?.raw_input),
      eventPresent: requestStarted !== undefined,
    },
    {
      label: "Backend response",
      source: "BackendResponded.response_text",
      value: stringOrNull((backendResponded as Record<string, unknown> | undefined)?.response_text),
      eventPresent: backendResponded !== undefined,
    },
  ];
}

function stringOrNull(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function badgeVariant(f: PayloadField): "default" | "secondary" | "outline" {
  if (f.value !== null) return "default";
  if (f.eventPresent) return "secondary";
  return "outline";
}

function statusFor(f: PayloadField): string {
  if (f.value !== null) return "captured";
  if (f.eventPresent) return "not captured";
  return "n/a";
}

function statusDetail(f: PayloadField): string {
  if (f.eventPresent) {
    return `Event was emitted but the field is empty — backend capture policy did not opt in for this request.`;
  }
  return `No ${f.source.split(".")[0]} event was emitted for this request.`;
}
