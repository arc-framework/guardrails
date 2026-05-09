/**
 * Fixture-mode API. Reads the static JSON files in apps/guardrail-flow/fixtures/
 * via Vite's import system and returns canned data wrapped in resolved
 * Promises. Filters are honored client-side against the fixture set so
 * the explorer's filter UX can be exercised without a backend.
 *
 * Routes that don't match a fixture file return a synthetic ApiError with
 * code "rid_not_found" — exercises the error-state UX (FR-014).
 */

import type {
  LifecycleReplay,
  RequestDebugPage,
  RequestDecisionEnvelope,
  RequestPage,
  RequestSummary,
  RequestWorkspaceManifest,
} from "@/types/api";
import type { DashboardApi, ListDebugParams, ListRequestsParams } from "./types";
import { ApiError } from "./types";

import requestsFixture from "../../../fixtures/requests.json";
import sampleManifest from "../../../fixtures/requests/01JFIXT0RID01.json";
import sampleDecision from "../../../fixtures/requests/01JFIXT0RID01/decision.json";
import sampleDebug from "../../../fixtures/requests/01JFIXT0RID01/debug.json";
import sampleEvents from "../../../fixtures/events.json";
import liveManifest from "../../../fixtures/requests/01JFIXT0LIVE01.json";
import liveEvents from "../../../fixtures/requests/01JFIXT0LIVE01/events.json";

const COMPLETED_RID = "01JFIXT0RID01";
const LIVE_RID = "01JFIXT0LIVE01";

const MANIFESTS_BY_RID: Record<string, RequestWorkspaceManifest> = {
  [COMPLETED_RID]: sampleManifest as unknown as RequestWorkspaceManifest,
  [LIVE_RID]: liveManifest as unknown as RequestWorkspaceManifest,
};

const EVENTS_BY_RID: Record<string, LifecycleReplay> = {
  [COMPLETED_RID]: sampleEvents as unknown as LifecycleReplay,
  [LIVE_RID]: liveEvents as unknown as LifecycleReplay,
};

function applyFilters(rows: RequestSummary[], params: ListRequestsParams): RequestSummary[] {
  let out = rows;
  if (params.since) {
    out = out.filter((r) => r.started_at >= params.since!);
  }
  if (params.until) {
    out = out.filter((r) => r.started_at < params.until!);
  }
  if (params.status && params.status.length > 0) {
    out = out.filter((r) => params.status!.includes(r.status));
  }
  if (params.action && params.action.length > 0) {
    out = out.filter((r) => r.final_action !== null && params.action!.includes(r.final_action));
  }
  if (params.risk_band && params.risk_band.length > 0) {
    out = out.filter((r) => {
      const max = r.max_risk;
      const bands = params.risk_band!;
      if (max === null || max < 0.5) return bands.includes("low");
      if (max < 0.85) return bands.includes("med");
      return bands.includes("high");
    });
  }
  if (params.rid_prefix !== undefined && params.rid_prefix !== "") {
    out = out.filter((r) => r.rid.startsWith(params.rid_prefix!));
  }
  return out;
}

export const fixtureApi: DashboardApi = {
  async listRequests(params) {
    const base = requestsFixture as unknown as RequestPage;
    const filtered = applyFilters(base.items, params);
    const page = params.page ?? 1;
    const pageSize = params.page_size ?? 50;
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const items = filtered.slice(start, end);
    return {
      items,
      page,
      page_size: pageSize,
      total: filtered.length,
      has_more: end < filtered.length,
      filters: {
        since: params.since ?? null,
        until: params.until ?? null,
        status: params.status ?? [],
        action: params.action ?? [],
        risk_band: params.risk_band ?? [],
        rid_prefix: params.rid_prefix ?? null,
      },
    };
  },

  async getRequestDetail(rid) {
    const manifest = MANIFESTS_BY_RID[rid];
    if (manifest) return manifest;
    throw new ApiError({
      code: "rid_not_found",
      message: `rid not found in fixture corpus`,
      status: 404,
    });
  },

  async getRequestDecision(rid) {
    if (rid === COMPLETED_RID) {
      return sampleDecision as unknown as RequestDecisionEnvelope;
    }
    throw new ApiError({
      code: "decision_not_captured",
      message: `no DecisionRecord recorded for rid ${rid}`,
      status: 404,
    });
  },

  async getRequestDebug(rid, _params: ListDebugParams) {
    if (rid === COMPLETED_RID || rid === LIVE_RID) {
      return sampleDebug as unknown as RequestDebugPage;
    }
    throw new ApiError({
      code: "debug_not_captured",
      message: `no debug entries recorded for rid ${rid}`,
      status: 404,
    });
  },

  async getLifecycleReplay(rid) {
    const replay = EVENTS_BY_RID[rid];
    if (replay) return replay;
    throw new ApiError({
      code: "rid_not_found",
      message: `rid not found in fixture corpus`,
      status: 404,
    });
  },
};
