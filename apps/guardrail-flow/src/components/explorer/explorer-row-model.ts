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

export function projectRow(summary: RequestSummary): ExplorerRowModel {
  return {
    summary,
    riskBand: bandFor(summary.max_risk),
    durationDisplay: durationDisplay(summary.duration_ms),
    liveBadge: summary.live,
    stageDisplay: summary.stage === null ? "—" : (STAGE_DISPLAY[summary.stage] ?? summary.stage),
  };
}
