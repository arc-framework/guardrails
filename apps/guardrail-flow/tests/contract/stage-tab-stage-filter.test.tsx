import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StageTab } from "@/components/workspace/inspector/StageTab";
import type { LifecycleEventBase } from "@/types/api";
import type { WorkflowNodeState } from "@/types/workflow";

vi.mock("@formkit/auto-animate/react", () => ({
  useAutoAnimate: () => [undefined],
}));

vi.mock("@/lib/state/ui-store", () => ({
  useUiStore: (selector: (state: { payloadVisibility: "masked" | "visible" }) => unknown) =>
    selector({ payloadVisibility: "masked" }),
}));

function makeEvent(event_type: string, fields: Record<string, unknown>): LifecycleEventBase {
  return {
    id: `evt-${event_type}-${String(fields.seq ?? 1)}`,
    parent_id: null,
    seq: Number(fields.seq ?? 1),
    ts: "2026-05-10T12:00:00Z",
    rid: "rid-014-stage-tab",
    event_type,
    ...fields,
  };
}

const SELECTED_NODE: WorkflowNodeState = {
  stage: "execute",
  state: "active",
  durationMs: 12,
  findingCount: 1,
  jailbreakHit: false,
  deceptionScore: null,
};

describe("StageTab stage resolution", () => {
  it("keeps detail events that belong to the selected stage even without a stage field", () => {
    render(
      <StageTab
        selectedNode={SELECTED_NODE}
        events={[
          makeEvent("StageRan", { seq: 1, stage: "execute", status: "ok", duration_ms: 12 }),
          makeEvent("StrategyExecuted", {
            seq: 2,
            strategy: "RedactStrategy",
            finding_id: "find-1",
            text_after_size: 21,
            text_before: "alice@example.com",
            text_after: "[EMAIL_ADDRESS]",
          }),
          makeEvent("BackendResponded", {
            seq: 3,
            duration_ms: 50,
            http_status: 200,
            response_finish_reason: "stop",
            response_text: "guarded output",
            token_usage: { total_tokens: 42 },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Events (3)")).toBeDefined();
    expect(screen.getByText("StrategyExecuted")).toBeDefined();
    expect(screen.getByText("BackendResponded")).toBeDefined();
    expect(screen.queryByText("No events recorded for this stage.")).toBeNull();
  });
});