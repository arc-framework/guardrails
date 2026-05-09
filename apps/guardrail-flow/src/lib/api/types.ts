/**
 * The DashboardApi interface that both client.ts (live) and fixtures.ts
 * (fixture mode) implement. Adding a new function to one and not the
 * other is a TS error.
 */

import type {
  FinalAction,
  LifecycleReplay,
  RequestDebugPage,
  RequestDecisionEnvelope,
  RequestPage,
  RequestStatus,
  RequestWorkspaceManifest,
  RiskBand,
} from "@/types/api";

export interface ListRequestsParams {
  page?: number;
  page_size?: number;
  since?: string;
  until?: string;
  status?: RequestStatus[];
  action?: FinalAction[];
  risk_band?: RiskBand[];
  rid_prefix?: string;
}

export interface ListDebugParams {
  page_size?: number;
  cursor?: string;
}

export interface DashboardApi {
  listRequests(params: ListRequestsParams): Promise<RequestPage>;
  getRequestDetail(rid: string): Promise<RequestWorkspaceManifest>;
  getRequestDecision(rid: string): Promise<RequestDecisionEnvelope>;
  getRequestDebug(rid: string, params: ListDebugParams): Promise<RequestDebugPage>;
  getLifecycleReplay(rid: string): Promise<LifecycleReplay>;
}

/**
 * Thrown by the API client when a non-2xx response is received OR when a
 * synthetic error is needed (e.g. fixture-mode "not found"). The `code`
 * matches the backend's documented error envelope code.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(opts: { code: string; message: string; status: number; retryAfter?: number | null }) {
    super(opts.message);
    this.name = "ApiError";
    this.code = opts.code;
    this.status = opts.status;
    this.retryAfter = opts.retryAfter ?? null;
  }
}

/**
 * Thrown by the live API client when fetch rejects with a TypeError that
 * looks like a CORS / network failure. Surfaced by the API client to the
 * <CorsErrorBanner> component so operators can fix their backend config.
 */
export class CorsLikelyError extends Error {
  readonly requestedUrl: string;
  readonly configuredOrigin: string;

  constructor(opts: { requestedUrl: string; configuredOrigin: string }) {
    super(
      `Cross-origin fetch to ${opts.requestedUrl} failed; this usually means ` +
        `the backend's dashboard_origins setting does not include the ` +
        `dashboard's origin (${opts.configuredOrigin}).`,
    );
    this.name = "CorsLikelyError";
    this.requestedUrl = opts.requestedUrl;
    this.configuredOrigin = opts.configuredOrigin;
  }
}
