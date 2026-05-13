/**
 * Mode-selecting API entry point. Both client.ts (live) and fixtures.ts
 * (fixture mode) implement the same DashboardApi interface; this module
 * picks one at import time based on the env mode and re-exports it as the
 * single `api` singleton consumed throughout the app.
 *
 * Switching mode requires a build-time env var change (VITE_DASHBOARD_MODE).
 * No in-app runtime toggle in Phase 1 — see research R8.
 */

import { mode } from "@/lib/env";
import { liveApi } from "./client";
import { fixtureApi } from "./fixtures";
import type { DashboardApi } from "./types";

export const api: DashboardApi = mode === "fixture" ? fixtureApi : liveApi;

export { ApiError, CorsLikelyError } from "./types";
export type { DashboardApi, ListDebugParams, ListRequestsParams } from "./types";
