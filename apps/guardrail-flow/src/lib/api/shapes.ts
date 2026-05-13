/**
 * Hand-rolled type narrowers (no zod dependency in Phase 1 — keeps the
 * bundle lean and the validation step trivial to read). Used by the
 * contract tests to assert fixture JSON parses cleanly into the
 * documented types; live callers trust the backend's contract tests
 * (Spec 012 ships 158+ contract tests for the wire format).
 *
 * The narrowers throw ApiError with code "shape_mismatch" on any
 * structural failure — surfaces to the FR-014 error state rather than
 * crashing a render.
 */

import type {
  ApiErrorEnvelope,
  RequestDebugPage,
  RequestDecisionEnvelope,
  RequestPage,
  RequestSummary,
  RequestWorkspaceManifest,
} from "@/types/api";
import { ApiError } from "./types";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function shapeError(field: string, expected: string): never {
  throw new ApiError({
    code: "shape_mismatch",
    message: `Expected ${expected} at ${field}`,
    status: 0,
  });
}

function requireString(obj: Record<string, unknown>, key: string): string {
  const v = obj[key];
  if (typeof v !== "string") shapeError(key, "string");
  return v as string;
}

function requireNumber(obj: Record<string, unknown>, key: string): number {
  const v = obj[key];
  if (typeof v !== "number") shapeError(key, "number");
  return v as number;
}

function requireBoolean(obj: Record<string, unknown>, key: string): boolean {
  const v = obj[key];
  if (typeof v !== "boolean") shapeError(key, "boolean");
  return v as boolean;
}

export function narrowRequestSummary(input: unknown): RequestSummary {
  if (!isObject(input)) shapeError("RequestSummary", "object");
  const o = input as Record<string, unknown>;
  return {
    rid: requireString(o, "rid"),
    started_at: requireString(o, "started_at"),
    last_event_at: requireString(o, "last_event_at"),
    status: requireString(o, "status") as RequestSummary["status"],
    final_action:
      o.final_action === null
        ? null
        : (requireString(o, "final_action") as RequestSummary["final_action"]),
    max_risk: o.max_risk === null ? null : requireNumber(o, "max_risk"),
    duration_ms: o.duration_ms === null ? null : requireNumber(o, "duration_ms"),
    refusal_code: o.refusal_code === null ? null : requireString(o, "refusal_code"),
    decision_id: o.decision_id === null ? null : requireString(o, "decision_id"),
    live: requireBoolean(o, "live"),
    stage: o.stage === null ? null : (requireString(o, "stage") as RequestSummary["stage"]),
  };
}

export function narrowRequestPage(input: unknown): RequestPage {
  if (!isObject(input)) shapeError("RequestPage", "object");
  const o = input as Record<string, unknown>;
  if (!Array.isArray(o.items)) shapeError("RequestPage.items", "array");
  return {
    items: (o.items as unknown[]).map(narrowRequestSummary),
    page: requireNumber(o, "page"),
    page_size: requireNumber(o, "page_size"),
    total: requireNumber(o, "total"),
    has_more: requireBoolean(o, "has_more"),
    // Trust the filters block structurally — operators rarely misshape it,
    // and the explorer uses it for round-trip display only.
    filters: (o.filters ?? {
      since: null,
      until: null,
      status: [],
      action: [],
      risk_band: [],
      rid_prefix: null,
    }) as unknown as RequestPage["filters"],
  };
}

export function narrowRequestWorkspaceManifest(input: unknown): RequestWorkspaceManifest {
  if (!isObject(input)) shapeError("RequestWorkspaceManifest", "object");
  const o = input as Record<string, unknown>;
  if (!isObject(o.summary)) shapeError("manifest.summary", "object");
  if (!isObject(o.resources)) shapeError("manifest.resources", "object");
  if (!isObject(o.links)) shapeError("manifest.links", "object");
  return {
    summary: narrowRequestSummary(o.summary),
    resources: o.resources as unknown as RequestWorkspaceManifest["resources"],
    links: o.links as unknown as RequestWorkspaceManifest["links"],
  };
}

export function narrowRequestDecisionEnvelope(input: unknown): RequestDecisionEnvelope {
  if (!isObject(input)) shapeError("RequestDecisionEnvelope", "object");
  const o = input as Record<string, unknown>;
  if (!isObject(o.decision)) shapeError("decision.decision", "object");
  return {
    rid: requireString(o, "rid"),
    decision_id: requireString(o, "decision_id"),
    recorded_at: requireString(o, "recorded_at"),
    decision: o.decision as Record<string, unknown>,
    payload_size_bytes: requireNumber(o, "payload_size_bytes"),
  };
}

export function narrowRequestDebugPage(input: unknown): RequestDebugPage {
  if (!isObject(input)) shapeError("RequestDebugPage", "object");
  const o = input as Record<string, unknown>;
  if (!Array.isArray(o.items)) shapeError("debug.items", "array");
  return {
    rid: requireString(o, "rid"),
    items: o.items as RequestDebugPage["items"],
    next_cursor: o.next_cursor === null ? null : requireString(o, "next_cursor"),
    page_size: requireNumber(o, "page_size"),
  };
}

export function isApiErrorEnvelope(input: unknown): input is ApiErrorEnvelope {
  if (!isObject(input)) return false;
  const err = (input as Record<string, unknown>).error;
  if (!isObject(err)) return false;
  return typeof err.code === "string" && typeof err.message === "string";
}
