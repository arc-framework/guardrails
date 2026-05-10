import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceRoute } from "@/routes/workspace";
import type { LifecycleEventBase, RequestWorkspaceManifest } from "@/types/api";

const mocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  setSearchParams: vi.fn(),
  setSelectedNodeId: vi.fn(),
  setInspectorTab: vi.fn(),
  setDockTab: vi.fn(),
  setLiveSse: vi.fn(),
  resetWorkspaceState: vi.fn(),
}));

const fixture = vi.hoisted(() => ({
  manifest: {
    summary: {
      rid: "rid-live-014",
      started_at: "2026-05-10T12:00:00Z",
      last_event_at: "2026-05-10T12:00:01Z",
      status: "live",
      final_action: null,
      max_risk: null,
      duration_ms: null,
      refusal_code: null,
      decision_id: null,
      live: true,
      stage: "route",
    },
    resources: {
      lifecycle: true,
      decision: false,
      debug: true,
      live_stream: true,
    },
    links: {
      lifecycle: "/lifecycle/rid-live-014",
      decision: "/decision/rid-live-014",
      debug: "/debug/rid-live-014",
      live_stream: "/events?rid=rid-live-014",
    },
  } satisfies RequestWorkspaceManifest,
  events: [
    {
      id: "evt-stage-1",
      parent_id: null,
      seq: 1,
      ts: "2026-05-10T12:00:00Z",
      rid: "rid-live-014",
      event_type: "StageRan",
      stage: "validate",
      status: "ok",
      duration_ms: 4,
    },
    {
      id: "evt-stage-2",
      parent_id: "evt-stage-1",
      seq: 2,
      ts: "2026-05-10T12:00:00.100Z",
      rid: "rid-live-014",
      event_type: "StageRan",
      stage: "sanitize",
      status: "ok",
      duration_ms: 12,
    },
  ] satisfies LifecycleEventBase[],
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>(
    "@tanstack/react-query",
  );
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
  };
});

vi.mock("react-router-dom", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  useParams: () => ({ rid: "rid-live-014" }),
  useSearchParams: () => [new URLSearchParams(), mocks.setSearchParams],
}));

vi.mock("@/lib/state/ui-store", () => ({
  useUiStore: (
    selector: (
      state: Record<string, unknown>,
    ) => unknown,
  ) =>
    selector({
      selectedNodeId: "route",
      setSelectedNodeId: mocks.setSelectedNodeId,
      inspectorTab: "stage",
      setInspectorTab: mocks.setInspectorTab,
      dockTab: "lifecycle",
      setDockTab: mocks.setDockTab,
      setLiveSse: mocks.setLiveSse,
      resetWorkspaceState: mocks.resetWorkspaceState,
    }),
}));

vi.mock("@/hooks/useRequestDetailQuery", () => ({
  useRequestDetailQuery: () => ({
    data: fixture.manifest,
    isError: false,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useLifecycleQuery", () => ({
  useLifecycleQuery: () => ({
    data: { events: fixture.events },
    isError: false,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useDecisionQuery", () => ({
  useDecisionQuery: () => ({ data: null, isLoading: false, isError: false, error: null }),
}));

vi.mock("@/hooks/useFilteredSSE", () => ({
  useFilteredSSE: () => ({ status: "live", lastEventId: null }),
}));

vi.mock("@/lib/state/query-client", () => ({
  invalidateOnSseEvent: vi.fn(),
}));

vi.mock("@/components/shared/ErrorState", () => ({
  ErrorState: () => <div>Error</div>,
}));

vi.mock("@/components/shared/LoadingState", () => ({
  LoadingState: () => <div>Loading</div>,
}));

vi.mock("@/components/shared/CorsErrorBanner", () => ({
  CorsErrorBanner: () => <div>CORS</div>,
}));

vi.mock("@/components/workspace/LifecycleCanvas", () => ({
  LifecycleCanvas: ({ activeStage }: { activeStage?: string | null }) => (
    <div data-testid="canvas-active-stage">{activeStage ?? "none"}</div>
  ),
}));

vi.mock("@/components/workspace/Inspector", () => ({
  Inspector: ({ selectedNode }: { selectedNode: { stage: string; state: string } | null }) => (
    <div data-testid="inspector-selected-node">
      {selectedNode ? `${selectedNode.stage}:${selectedNode.state}` : "none"}
    </div>
  ),
}));

vi.mock("@/components/workspace/DebugDock", () => ({
  DebugDock: () => <div>DebugDock</div>,
}));

describe("WorkspaceRoute live stage wiring", () => {
  it("passes the live summary stage into the canvas and selected-node state", () => {
    render(<WorkspaceRoute />);

    expect(screen.getByTestId("canvas-active-stage").textContent).toBe("route");
    expect(screen.getByTestId("inspector-selected-node").textContent).toBe("route:active");
  });
});