import { useCallback, useEffect, useRef } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useUiStore } from "@/lib/state/ui-store";
import { cn } from "@/lib/utils";
import type { LifecycleEventBase } from "@/types/api";
import type { DebugTab } from "@/types/workflow";
import { LifecycleSSETab } from "./dock/LifecycleSSETab";
import { LogsTab } from "./dock/LogsTab";
import { BackendTab } from "./dock/BackendTab";
import { DiffReplayTab } from "./dock/DiffReplayTab";

export interface DebugDockProps {
  rid: string;
  events: LifecycleEventBase[];
  sseStatus: "idle" | "connecting" | "live" | "throttled" | "terminated" | "error";
  activeTab: DebugTab;
  onTabChange: (tab: DebugTab) => void;
}

const TAB_LABELS: Record<DebugTab, string> = {
  lifecycle: "Lifecycle SSE",
  logs: "Logs",
  backend: "Backend",
  diff_replay: "Diff/Replay",
};

/**
 * Per-tab data presence. Greys the tab trigger when there is nothing to
 * render; trigger remains clickable so the operator can confirm the
 * documented empty state.
 */
function dockTabHasData(tab: DebugTab, events: LifecycleEventBase[]): boolean {
  switch (tab) {
    case "lifecycle":
      return events.length > 0;
    case "logs":
      // Always reachable — the panel calls useDebugQuery which has its own
      // empty/error states. We don't have synchronous access to the debug
      // entries here. Default true so the tab isn't greyed prematurely.
      return true;
    case "backend":
      return events.some(
        (e) => e.event_type === "BackendCalled" || e.event_type === "BackendResponded",
      );
    case "diff_replay":
      // Has data when at least one transformative event carries both a
      // ``text_before`` and ``text_after`` (capture flags must be on).
      return events.some((e) => {
        const r = e as Record<string, unknown>;
        return (
          (e.event_type === "SanitizationApplied" ||
            e.event_type === "StrategyExecuted" ||
            e.event_type === "PayloadRewritten" ||
            e.event_type === "RehydrationVerified") &&
          typeof r.text_before === "string" &&
          typeof r.text_after === "string"
        );
      });
    default:
      return true;
  }
}

const COLLAPSED_HEIGHT_PX = 36;

export function DebugDock({ rid, events, sseStatus, activeTab, onTabChange }: DebugDockProps) {
  const collapsed = useUiStore((s) => s.dockCollapsed);
  const setCollapsed = useUiStore((s) => s.setDockCollapsed);
  const heightPx = useUiStore((s) => s.dockHeightPx);
  const setHeightPx = useUiStore((s) => s.setDockHeightPx);

  const dragOriginRef = useRef<{ y: number; height: number } | null>(null);

  const onDragStart = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      dragOriginRef.current = { y: e.clientY, height: heightPx };
    },
    [heightPx],
  );

  const onDragMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragOriginRef.current) return;
      const dy = dragOriginRef.current.y - e.clientY;
      setHeightPx(dragOriginRef.current.height + dy);
    },
    [setHeightPx],
  );

  const onDragEnd = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    dragOriginRef.current = null;
  }, []);

  useEffect(
    () => () => {
      dragOriginRef.current = null;
    },
    [],
  );

  return (
    <section
      className="flex flex-col rounded-md border bg-card"
      style={{ height: collapsed ? COLLAPSED_HEIGHT_PX : heightPx }}
    >
      {!collapsed ? (
        <div
          role="separator"
          aria-orientation="horizontal"
          className="h-1 cursor-ns-resize bg-border hover:bg-primary/40"
          onPointerDown={onDragStart}
          onPointerMove={onDragMove}
          onPointerUp={onDragEnd}
        />
      ) : null}
      <div className="flex items-center justify-between px-3 py-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Debug Dock
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand debug dock" : "Collapse debug dock"}
        >
          {collapsed ? "↑" : "↓"}
        </Button>
      </div>
      {!collapsed ? (
        <>
          <Separator />
          <Tabs
            value={activeTab}
            onValueChange={(v) => onTabChange(v as DebugTab)}
            className="flex min-h-0 flex-1 flex-col"
          >
            <TabsList className="mx-3 mt-2 grid w-fit grid-cols-4">
              {(Object.keys(TAB_LABELS) as DebugTab[]).map((tab) => {
                const hasData = dockTabHasData(tab, events);
                return (
                  <TabsTrigger
                    key={tab}
                    value={tab}
                    className={cn(
                      "text-xs",
                      !hasData &&
                        "text-muted-foreground/60 data-[state=active]:text-muted-foreground",
                    )}
                    title={hasData ? undefined : `${TAB_LABELS[tab]} — no data captured`}
                  >
                    {TAB_LABELS[tab]}
                  </TabsTrigger>
                );
              })}
            </TabsList>
            <TabsContent value="lifecycle" className="mt-2 min-h-0 flex-1 overflow-auto px-3 pb-3">
              <LifecycleSSETab events={events} sseStatus={sseStatus} />
            </TabsContent>
            <TabsContent value="logs" className="mt-2 min-h-0 flex-1 overflow-auto px-3 pb-3">
              <LogsTab rid={rid} />
            </TabsContent>
            <TabsContent value="backend" className="mt-2 min-h-0 flex-1 overflow-auto px-3 pb-3">
              <BackendTab events={events} />
            </TabsContent>
            <TabsContent
              value="diff_replay"
              className="mt-2 min-h-0 flex-1 overflow-auto px-3 pb-3"
            >
              <DiffReplayTab events={events} />
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </section>
  );
}
