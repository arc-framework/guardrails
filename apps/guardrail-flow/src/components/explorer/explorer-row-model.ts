import type { RequestSummary, RiskBand } from "@/types/api";
import type { ExplorerRowModel } from "@/types/workflow";

const STAGE_DISPLAY: Record<string, string> = {
  validate: "Validate",
  defend: "Defend",
  classify: "Classify",
  deception_inspect: "Deception",
  sanitize: "Sanitize",
  route: "Route",
  execute: "Execute",
  refusal: "Refusal",
  verify: "Verify",
  rehydrate: "Rehydrate",
  decision_emit: "Decision",
  report: "Report",
};

function bandFor(maxRisk: number | null): RiskBand | null {
  if (maxRisk === null) return null;
  if (maxRisk < 0.5) return "low";
  if (maxRisk < 0.85) return "med";
  return "high";
}

function durationDisplay(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/** Defense-in-depth client threshold for the ⚠ stale tag. Deliberately
 *  looser than the server-side sweeper default (10 minutes) so the
 *  sweeper has time to act before the client-side warning appears. */
const CLIENT_STALE_THRESHOLD_MS = 30 * 60 * 1000;

function isStale(summary: RequestSummary, now: number): boolean {
  if (!summary.live) return false;
  const last = Date.parse(summary.last_event_at);
  if (Number.isNaN(last)) return false;
  return now - last > CLIENT_STALE_THRESHOLD_MS;
}

export function projectRow(summary: RequestSummary): ExplorerRowModel {
  const now = Date.now();
  return {
    summary,
    riskBand: bandFor(summary.max_risk),
    durationDisplay: durationDisplay(summary.duration_ms),
    liveBadge: summary.live,
    staleBadge: isStale(summary, now),
    stageDisplay: summary.stage === null ? "—" : (STAGE_DISPLAY[summary.stage] ?? summary.stage),
  };
}
