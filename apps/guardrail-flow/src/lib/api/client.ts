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
import type { ChatCompletionResult, ChatExamplePreset } from "@/types/chat";
import type {
  DashboardApi,
  ListDebugParams,
  ListRequestsParams,
  SendChatCompletionInput,
} from "./types";
import { ApiError, CorsLikelyError } from "./types";

interface ChatCompletionApiEnvelope {
  id?: string;
  model?: string;
  choices?: Array<{
    finish_reason?: string | null;
    message?: {
      content?: string | null;
    };
  }>;
  arc_guard?: {
    rid?: string | null;
    blocked?: boolean;
    blocked_phase?: "pre_process" | "post_process" | null;
    pre_process?: {
      action?: string | null;
    };
    post_process?: {
      action?: string | null;
    };
  };
}

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

async function performRequest(path: string, init: RequestInit): Promise<Response> {
  const url = `${baseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, { credentials: "omit", ...init });
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

  return response;
}

async function parseResponse<T>(response: Response): Promise<T> {
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

async function request<T>(path: string): Promise<T> {
  const response = await performRequest(path, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return parseResponse<T>(response);
}

async function requestWithResponse<T>(
  path: string,
  init: RequestInit,
): Promise<{ data: T; response: Response }> {
  const response = await performRequest(path, init);
  const data = await parseResponse<T>(response);
  return { data, response };
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
  listChatExamples() {
    return request<ChatExamplePreset[]>("/chat/examples");
  },
  async sendChatCompletion(input: SendChatCompletionInput) {
    const { data, response } = await requestWithResponse<ChatCompletionApiEnvelope>(
      "/v1/chat/completions",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Request-Id": input.requestId,
        },
        body: JSON.stringify(input.body),
      },
    );

    const firstChoice = data.choices?.[0];
    return {
      requestId: input.requestId,
      rid: data.arc_guard?.rid ?? response.headers.get("x-request-id") ?? input.requestId,
      responseId: data.id ?? input.requestId,
      model: data.model ?? input.body.model,
      assistantMessage: firstChoice?.message?.content ?? "",
      finishReason: firstChoice?.finish_reason ?? null,
      blocked: Boolean(data.arc_guard?.blocked),
      blockedPhase: data.arc_guard?.blocked_phase ?? null,
      preAction: data.arc_guard?.pre_process?.action ?? null,
      postAction: data.arc_guard?.post_process?.action ?? null,
    } satisfies ChatCompletionResult;
  },
};
