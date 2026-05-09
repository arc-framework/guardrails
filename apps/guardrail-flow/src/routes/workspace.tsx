import { useCallback, useEffect, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { CorsErrorBanner } from "@/components/shared/CorsErrorBanner";
import { LifecycleCanvas } from "@/components/workspace/LifecycleCanvas";
import { Inspector } from "@/components/workspace/Inspector";
import { DebugDock } from "@/components/workspace/DebugDock";
import { useRequestDetailQuery } from "@/hooks/useRequestDetailQuery";
import { useLifecycleQuery } from "@/hooks/useLifecycleQuery";
import { useDecisionQuery } from "@/hooks/useDecisionQuery";
import { useFilteredSSE } from "@/hooks/useFilteredSSE";
import { CorsLikelyError } from "@/lib/api";
import { invalidateOnSseEvent } from "@/lib/state/query-client";
import { useUiStore } from "@/lib/state/ui-store";
import { deriveNodeStates } from "@/lib/workflow/derive-node-state";
import type { StageName } from "@/types/api";
import type { DebugTab, InspectorTab } from "@/types/workflow";

const RID_REGEX = /^[A-Za-z0-9._-]{1,64}$/;
const INSPECTOR_TABS: readonly InspectorTab[] = ["stage", "decision", "policy", "payload", "json"];
const DEBUG_TABS: readonly DebugTab[] = ["lifecycle", "logs", "backend", "diff_replay"];

function isInspectorTab(v: string | null): v is InspectorTab {
  return !!v && (INSPECTOR_TABS as readonly string[]).includes(v);
}

function isDebugTab(v: string | null): v is DebugTab {
  return !!v && (DEBUG_TABS as readonly string[]).includes(v);
}

export function WorkspaceRoute() {
  const { rid: ridParam } = useParams<{ rid: string }>();
  const rid = ridParam ?? "";
  const ridValid = RID_REGEX.test(rid);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const setSelectedNodeId = useUiStore((s) => s.setSelectedNodeId);
  const inspectorTabFromStore = useUiStore((s) => s.inspectorTab);
  const setInspectorTab = useUiStore((s) => s.setInspectorTab);
  const dockTabFromStore = useUiStore((s) => s.dockTab);
  const setDockTab = useUiStore((s) => s.setDockTab);
  const setLiveSse = useUiStore((s) => s.setLiveSse);
  const resetWorkspaceState = useUiStore((s) => s.resetWorkspaceState);

  // Reset volatile workspace state when the rid changes so a different
  // request doesn't inherit the previous one's selection / tab focus.
  useEffect(() => {
    resetWorkspaceState();
  }, [rid, resetWorkspaceState]);

  const inspectorTab: InspectorTab = isInspectorTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as InspectorTab)
    : inspectorTabFromStore;
  const dockTab: DebugTab = isDebugTab(searchParams.get("dock"))
    ? (searchParams.get("dock") as DebugTab)
    : dockTabFromStore;

  useEffect(() => {
    setInspectorTab(inspectorTab);
  }, [inspectorTab, setInspectorTab]);
  useEffect(() => {
    setDockTab(dockTab);
  }, [dockTab, setDockTab]);

  const onInspectorTabChange = useCallback(
    (tab: InspectorTab) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", tab);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const onDockTabChange = useCallback(
    (tab: DebugTab) => {
      const next = new URLSearchParams(searchParams);
      next.set("dock", tab);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const detail = useRequestDetailQuery(ridValid ? rid : undefined);
  const lifecycle = useLifecycleQuery(ridValid ? rid : undefined);
  const decisionAvailable = detail.data?.resources.decision ?? false;
  const decision = useDecisionQuery(ridValid ? rid : undefined, decisionAvailable);

  const isLive = detail.data?.summary.live ?? false;

  const sse = useFilteredSSE({
    rid,
    enabled: ridValid && isLive,
    onEvent: (event) => invalidateOnSseEvent(queryClient, rid, event),
    onTerminated: () => {
      void queryClient.invalidateQueries({ queryKey: ["request", rid] });
    },
    onError: () => {
      // Status surfaced via sse.status badge in the header.
    },
  });

  // Publish SSE status to the global UI store so the App shell can render
  // a live-follow badge without needing to know which rid is being viewed.
  useEffect(() => {
    setLiveSse(rid || null, sse.status);
    return () => setLiveSse(null, "idle");
  }, [rid, sse.status, setLiveSse]);

  const events = useMemo(() => lifecycle.data?.events ?? [], [lifecycle.data?.events]);
  const nodeStates = useMemo(() => deriveNodeStates(events), [events]);
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    const stage = selectedNodeId as StageName;
    return nodeStates[stage] ?? null;
  }, [selectedNodeId, nodeStates]);

  if (!ridValid) {
    return (
      <div className="p-4">
        <ErrorState error={new Error(`rid "${rid}" must match [A-Za-z0-9._-]{1,64}`)} />
      </div>
    );
  }

  if (detail.isError) {
    if (detail.error instanceof CorsLikelyError) {
      return (
        <div className="p-4">
          <CorsErrorBanner error={detail.error} />
        </div>
      );
    }
    return (
      <div className="p-4">
        <ErrorState error={detail.error} onRetry={() => detail.refetch()} />
      </div>
    );
  }

  if (detail.isLoading || !detail.data) {
    return (
      <div className="p-4">
        <LoadingState rows={6} rowHeight="h-12" />
      </div>
    );
  }

  const manifest = detail.data;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-3 p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/requests" className="text-sm text-muted-foreground hover:underline">
            ← Requests
          </Link>
          <Separator orientation="vertical" className="h-6" />
          <h1 className="font-mono text-sm">{manifest.summary.rid}</h1>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {manifest.summary.live ? (
            <Badge variant="default" className="animate-pulse" aria-label={`live (${sse.status})`}>
              live · {sse.status}
            </Badge>
          ) : (
            <Badge variant="outline">{manifest.summary.status}</Badge>
          )}
          {sse.status === "terminated" && !manifest.summary.live ? (
            <Badge variant="secondary">request completed</Badge>
          ) : null}
          {manifest.summary.final_action ? (
            <Badge
              variant={
                manifest.summary.final_action === "block" ||
                manifest.summary.final_action === "refuse"
                  ? "destructive"
                  : "secondary"
              }
            >
              {manifest.summary.final_action}
            </Badge>
          ) : null}
          {manifest.summary.duration_ms !== null ? (
            <span className="text-muted-foreground">{manifest.summary.duration_ms} ms</span>
          ) : null}
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <div className="min-h-0 min-w-0 flex-1 rounded-md border bg-card lg:flex-[9_1_0%]">
          {lifecycle.isError ? (
            <div className="p-4">
              <ErrorState error={lifecycle.error} onRetry={() => lifecycle.refetch()} />
            </div>
          ) : lifecycle.isLoading || !lifecycle.data ? (
            <div className="p-4">
              <LoadingState rows={5} rowHeight="h-12" />
            </div>
          ) : (
            <LifecycleCanvas
              events={events}
              selectedNodeId={selectedNodeId}
              onNodeSelect={setSelectedNodeId}
            />
          )}
        </div>

        <Inspector
          manifest={manifest}
          events={events}
          selectedNode={selectedNode}
          decision={decision.data ?? null}
          decisionLoading={decision.isLoading}
          decisionError={decision.isError ? (decision.error as Error) : null}
          activeTab={inspectorTab}
          onTabChange={onInspectorTabChange}
        />
      </div>

      <DebugDock
        rid={rid}
        events={events}
        sseStatus={sse.status}
        activeTab={dockTab}
        onTabChange={onDockTabChange}
      />
    </div>
  );
}
