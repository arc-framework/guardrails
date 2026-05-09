/**
 * Live HTTP client implementing DashboardApi against the Python backend.
 * Reads VITE_DASHBOARD_API_URL at module init; serializes filter params
 * per the documented Spec 012 wire format (repeated arrays for multi-select);
 * maps 4xx/5xx to ApiError; maps fetch TypeErrors to CorsLikelyError.
 */

import { env } from "@/lib/env";
import type {
  ApiErrorEnvelope,
  LifecycleReplay,
  RequestDebugPage,
  RequestDecisionEnvelope,
  RequestPage,
  RequestWorkspaceManifest,
} from "@/types/api";
import type { DashboardApi, ListDebugParams, ListRequestsParams } from "./types";
import { ApiError, CorsLikelyError } from "./types";

function baseUrl(): string {
  if (env.apiUrl === null) {
    throw new Error("Live API client constructed in fixture mode (env bug)");
  }
  return env.apiUrl;
}

function serializeListRequests(params: ListRequestsParams): URLSearchParams {
  const sp = new URLSearchParams();
  if (params.page !== undefined) sp.set("page", String(params.page));
  if (params.page_size !== undefined) sp.set("page_size", String(params.page_size));
  if (params.since !== undefined && params.since !== "") sp.set("since", params.since);
  if (params.until !== undefined && params.until !== "") sp.set("until", params.until);
  for (const s of params.status ?? []) sp.append("status", s);
  for (const a of params.action ?? []) sp.append("action", a);
  for (const r of params.risk_band ?? []) sp.append("risk_band", r);
  if (params.rid_prefix !== undefined && params.rid_prefix !== "")
    sp.set("rid_prefix", params.rid_prefix);
  return sp;
}

function serializeListDebug(params: ListDebugParams): URLSearchParams {
  const sp = new URLSearchParams();
  if (params.page_size !== undefined) sp.set("page_size", String(params.page_size));
  if (params.cursor !== undefined && params.cursor !== "") sp.set("cursor", params.cursor);
  return sp;
}

async function request<T>(path: string): Promise<T> {
  const url = `${baseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
    });
  } catch (cause) {
    // fetch() rejects with TypeError on network / CORS failures. There's
    // no reliable way to disambiguate CORS from offline, so we report the
    // common-misconfig case (CORS) and let the operator's diagnostics
    // disconfirm if needed.
    if (cause instanceof TypeError) {
      throw new CorsLikelyError({
        requestedUrl: url,
        configuredOrigin: window.location.origin,
      });
    }
    throw cause;
  }

  if (response.ok) {
    return (await response.json()) as T;
  }

  // Non-2xx: parse as ApiErrorEnvelope; fall back to a generic error if
  // the body is malformed.
  let envelope: ApiErrorEnvelope | null = null;
  try {
    envelope = (await response.json()) as ApiErrorEnvelope;
  } catch {
    envelope = null;
  }
  const retryAfterHeader = response.headers.get("Retry-After");
  const retryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) || null : null;
  throw new ApiError({
    code: envelope?.error?.code ?? "http_error",
    message: envelope?.error?.message ?? `${response.status} ${response.statusText}`,
    status: response.status,
    retryAfter,
  });
}

export const liveApi: DashboardApi = {
  listRequests(params) {
    const qs = serializeListRequests(params);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<RequestPage>(`/requests${suffix}`);
  },
  getRequestDetail(rid) {
    return request<RequestWorkspaceManifest>(`/requests/${encodeURIComponent(rid)}`);
  },
  getRequestDecision(rid) {
    return request<RequestDecisionEnvelope>(`/requests/${encodeURIComponent(rid)}/decision`);
  },
  getRequestDebug(rid, params) {
    const qs = serializeListDebug(params);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<RequestDebugPage>(`/requests/${encodeURIComponent(rid)}/debug${suffix}`);
  },
  getLifecycleReplay(rid) {
    return request<LifecycleReplay>(`/lifecycle/${encodeURIComponent(rid)}`);
  },
};
