import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { JsonView } from "@/components/shared/JsonView";
import type { BackendCalledEvent, BackendRespondedEvent, LifecycleEventBase } from "@/types/api";

export interface BackendTabProps {
  events: LifecycleEventBase[];
}

export function BackendTab({ events }: BackendTabProps) {
  const called = findCalled(events);
  const responded = findResponded(events);

  if (!called && !responded) {
    return (
      <p className="text-xs text-muted-foreground">
        No backend round-trip recorded for this request.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <Pane title="BackendCalled">
        {called ? (
          <>
            <Field label="backend">
              <Badge variant="secondary">{called.backend}</Badge>
            </Field>
            <Field label="url">
              <span className="font-mono">{called.url}</span>
            </Field>
            <Field label="payload msgs">{called.payload_msg_count}</Field>
            <Separator />
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              model_config_snapshot
            </p>
            <JsonView value={called.model_config_snapshot ?? {}} maxHeight="200px" />
          </>
        ) : (
          <p className="text-xs text-muted-foreground">Not called.</p>
        )}
      </Pane>
      <Pane title="BackendResponded">
        {responded ? (
          <>
            <Field label="status">
              <Badge variant={responded.http_status >= 400 ? "destructive" : "default"}>
                {responded.http_status}
              </Badge>
            </Field>
            <Field label="duration">{responded.duration_ms} ms</Field>
            <Separator />
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              token_usage
            </p>
            <JsonView value={responded.token_usage ?? {}} maxHeight="200px" />
          </>
        ) : (
          <p className="text-xs text-muted-foreground">Not responded.</p>
        )}
      </Pane>
    </div>
  );
}

function Pane({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded border bg-background p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function findCalled(events: LifecycleEventBase[]): BackendCalledEvent | null {
  return (
    (events.find((e) => e.event_type === "BackendCalled") as BackendCalledEvent | undefined) ?? null
  );
}

function findResponded(events: LifecycleEventBase[]): BackendRespondedEvent | null {
  return (
    (events.find((e) => e.event_type === "BackendResponded") as
      | BackendRespondedEvent
      | undefined) ?? null
  );
}
