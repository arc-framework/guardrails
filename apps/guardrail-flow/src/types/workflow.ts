/**
 * UI-facing entities. Derived from the API types in `./api.ts` plus
 * UI state. These are the four key entities documented in the spec
 * (ExplorerRowModel, WorkflowNodeState, InspectorPaneModel, DebugDockModel).
 */

import type {
  BackendCalledEvent,
  BackendRespondedEvent,
  LifecycleEventBase,
  RequestDebugEntry,
  RequestDecisionEnvelope,
  RequestSummary,
  RiskBand,
  StageName,
} from "./api";

// ---------------------------------------------------------------------------
// Explorer row
// ---------------------------------------------------------------------------

export interface ExplorerRowModel {
  summary: RequestSummary;
  riskBand: RiskBand | null;
  durationDisplay: string;
  liveBadge: boolean;
  stageDisplay: string;
}

// ---------------------------------------------------------------------------
// Workflow canvas node state
// ---------------------------------------------------------------------------

export type NodeState = "inactive" | "active" | "completed" | "skipped" | "blocked" | "errored";

export interface WorkflowNodeState {
  stage: StageName;
  state: NodeState;
  durationMs: number | null;
  findingCount: number;
  jailbreakHit: boolean;
  deceptionScore: number | null;
}

// ---------------------------------------------------------------------------
// Inspector pane
// ---------------------------------------------------------------------------

export type InspectorTab = "stage" | "decision" | "policy" | "json" | "payload";

export interface InspectorPaneModel {
  activeTab: InspectorTab;
  selectedNode: WorkflowNodeState | null;
  stageEvents: LifecycleEventBase[];
  decision: RequestDecisionEnvelope | null;
  policyView: {
    rules: Array<{ id: string; matched: boolean; action: string }>;
  } | null;
}

// ---------------------------------------------------------------------------
// Debug dock
// ---------------------------------------------------------------------------

export type DebugTab = "lifecycle" | "logs" | "backend" | "diff_replay";

export interface DebugDockModel {
  activeTab: DebugTab;
  lifecycleEvents: LifecycleEventBase[];
  logs: RequestDebugEntry[];
  backend: {
    called: BackendCalledEvent | null;
    responded: BackendRespondedEvent | null;
  };
  diffReplay: {
    available: false;
  };
  collapsed: boolean;
}
