/**
 * TypeScript types mirroring the dashboard data plane's pydantic envelopes
 * from the backend. The dashboard never converts ISO strings to Date at
 * the parsing layer — components do that conversion at render time if
 * needed. This keeps cache-key serialization predictable for TanStack Query.
 *
 * The contract test `tests/contract/shapes-match-backend.test.ts` validates
 * these types against the fixture-mode JSON; a backend shape change that
 * breaks a dashboard parsing assumption fails that test.
 */

// ---------------------------------------------------------------------------
// Literal-union aliases
// ---------------------------------------------------------------------------

export type RequestStatus = "live" | "completed" | "errored";

export type FinalAction = "pass" | "block" | "redact" | "clarify" | "refuse";

export type RiskBand = "low" | "med" | "high";

/**
 * The 12 stages of the guardrail pipeline. Stays in sync with the backend's
 * STAGE_DESCRIPTORS via the contract test.
 */
export type StageName =
  | "validate"
  | "defend"
  | "classify"
  | "deception_inspect"
  | "sanitize"
  | "route"
  | "execute"
  | "refusal"
  | "verify"
  | "rehydrate"
  | "decision_emit"
  | "report";

export type DebugSeverity = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

// ---------------------------------------------------------------------------
// Request summary / page (explorer)
// ---------------------------------------------------------------------------

export interface RequestSummary {
  rid: string;
  started_at: string;
  last_event_at: string;
  status: RequestStatus;
  final_action: FinalAction | null;
  max_risk: number | null;
  duration_ms: number | null;
  refusal_code: string | null;
  decision_id: string | null;
  live: boolean;
  stage: StageName | null;
}

export interface RequestPageFilters {
  since: string | null;
  until: string | null;
  status: RequestStatus[];
  action: FinalAction[];
  risk_band: RiskBand[];
  rid_prefix: string | null;
}

export interface RequestPage {
  items: RequestSummary[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  filters: RequestPageFilters;
}

// ---------------------------------------------------------------------------
// Request workspace manifest (workspace open)
// ---------------------------------------------------------------------------

export interface WorkspaceResourcesAvailability {
  lifecycle: boolean;
  decision: boolean;
  debug: boolean;
  live_stream: boolean;
}

export interface WorkspaceResourceLinks {
  lifecycle: string;
  decision: string;
  debug: string;
  live_stream: string;
}

export interface RequestWorkspaceManifest {
  summary: RequestSummary;
  resources: WorkspaceResourcesAvailability;
  links: WorkspaceResourceLinks;
}

// ---------------------------------------------------------------------------
// Decision + debug envelopes
// ---------------------------------------------------------------------------

export interface RequestDecisionEnvelope {
  rid: string;
  decision_id: string;
  recorded_at: string;
  decision: Record<string, unknown>;
  payload_size_bytes: number;
}

export interface RequestDebugEntry {
  rid: string;
  seq: number;
  ts: string;
  channel: string;
  severity: DebugSeverity;
  message: string;
  metadata: Record<string, unknown>;
}

export interface RequestDebugPage {
  rid: string;
  items: RequestDebugEntry[];
  next_cursor: string | null;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Lifecycle events (subset rendered distinctly; others fall through to JSON)
// ---------------------------------------------------------------------------

export interface LifecycleEventBase {
  id: string;
  parent_id: string | null;
  seq: number;
  ts: string;
  rid: string;
  event_type: string;
  [key: string]: unknown;
}

export interface JailbreakDetectedEvent extends LifecycleEventBase {
  event_type: "JailbreakDetected";
  detector_id: string;
  category: string;
  confidence: number;
  evidence_reference: string | null;
}

export interface DeceptionScoredEvent extends LifecycleEventBase {
  event_type: "DeceptionScored";
  score_value: number | null;
  score_sentinel: string | null;
  band: "not_measured" | "low" | "medium" | "high";
  marker_counts: Record<string, number> | null;
}

export interface BackendCalledEvent extends LifecycleEventBase {
  event_type: "BackendCalled";
  backend: "echo" | "ollama" | "openai";
  url: string;
  payload_msg_count: number;
  model_config_snapshot: Record<string, string | number> | null;
}

export interface BackendRespondedEvent extends LifecycleEventBase {
  event_type: "BackendResponded";
  duration_ms: number;
  http_status: number;
  token_usage: Record<string, number> | null;
}

export interface TerminatedSentinel {
  rid: string;
  reason: "completed" | "already_completed" | "errored";
}

// ---------------------------------------------------------------------------
// Lifecycle replay envelope (Spec 010)
// ---------------------------------------------------------------------------

export interface LifecycleReplay {
  rid: string;
  captured_at: string;
  served_from: string;
  phases: string[];
  events: LifecycleEventBase[];
}

// ---------------------------------------------------------------------------
// Error envelope
// ---------------------------------------------------------------------------

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
  };
}
