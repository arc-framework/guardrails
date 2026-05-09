import { useState } from "react";
import { useAutoAnimate } from "@formkit/auto-animate/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JsonView } from "@/components/shared/JsonView";
import type { LifecycleEventBase } from "@/types/api";

export interface LifecycleSSETabProps {
  events: LifecycleEventBase[];
  sseStatus: "idle" | "connecting" | "live" | "throttled" | "terminated" | "error";
}

const STATUS_VARIANT: Record<
  LifecycleSSETabProps["sseStatus"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  idle: "outline",
  connecting: "secondary",
  live: "default",
  throttled: "secondary",
  terminated: "outline",
  error: "destructive",
};

export function LifecycleSSETab({ events, sseStatus }: LifecycleSSETabProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [listRef] = useAutoAnimate<HTMLUListElement>();

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <header className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{events.length} events</span>
        <Badge variant={STATUS_VARIANT[sseStatus]}>{sseStatus}</Badge>
      </header>
      {events.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No lifecycle events yet — the request may not have started, or the lifecycle sink is not
          enabled on this backend.
        </p>
      ) : (
        <ul ref={listRef} className="space-y-1">
          {events.map((event) => {
            const isOpen = expanded.has(event.id);
            return (
              <li key={event.id} className="rounded border bg-background">
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex w-full items-center justify-between rounded-none px-2 text-left text-xs"
                  onClick={() => toggle(event.id)}
                >
                  <span className="font-mono">{event.event_type}</span>
                  <span className="text-muted-foreground">
                    seq {event.seq} · {event.ts}
                  </span>
                </Button>
                {isOpen ? (
                  <div className="border-t p-1">
                    <JsonView value={event} maxHeight="200px" />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
