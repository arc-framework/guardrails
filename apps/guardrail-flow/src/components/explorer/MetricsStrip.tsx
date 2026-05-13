import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { FinalAction, RequestSummary, RiskBand, StageName } from "@/types/api";
import { Fragment, useMemo, type ReactNode } from "react";
import { AreaSparklineChart, FunnelChart, FunnelSeries } from "reaviz";

export interface MetricsStripProps {
  rows: RequestSummary[];
  matrixRows?: RequestSummary[];
  totalMatching?: number;
  activeActionFilters?: FinalAction[];
  activeRiskFilters?: RiskBand[];
  onActionFilter?: (action: FinalAction) => void;
  onRiskFilter?: (band: RiskBand) => void;
}

const ACTION_ORDER: FinalAction[] = ["pass", "redact", "clarify", "block", "refuse"];
const RISK_ORDER: RiskBand[] = ["low", "med", "high"];
const ACTION_COLORS: Record<FinalAction, string> = {
  pass: "#10b981", // emerald
  redact: "#f59e0b", // amber
  clarify: "#3b82f6", // blue
  block: "#ef4444", // red
  refuse: "#dc2626", // dark red
};

const RISK_TINTS: Record<RiskBand, [number, number, number]> = {
  low: [16, 185, 129],
  med: [245, 158, 11],
  high: [239, 68, 68],
};

type LiveStageBucket = StageName | "pending";

const STAGE_ORDER: LiveStageBucket[] = [
  "pending",
  "validate",
  "defend",
  "classify",
  "deception_inspect",
  "sanitize",
  "route",
  "execute",
  "refusal",
  "verify",
  "rehydrate",
  "decision_emit",
  "report",
];

const STAGE_LABELS: Record<LiveStageBucket, string> = {
  pending: "Pending",
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

const CLIENT_STALE_THRESHOLD_MS = 30 * 60 * 1000;

export function MetricsStrip({
  rows,
  matrixRows,
  totalMatching,
  activeActionFilters = [],
  activeRiskFilters = [],
  onActionFilter,
  onRiskFilter,
}: MetricsStripProps) {
  const stats = useMemo(() => {
    const now = Date.now();
    const visibleCount = rows.length;
    const matchingCount = totalMatching ?? visibleCount;
    const matrixSourceRows = matrixRows ?? rows;
    const liveCount = rows.filter((r) => r.live).length;
    const erroredCount = rows.filter((r) => r.status === "errored").length;
    const staleLiveCount = rows.filter((r) => isStale(r, now)).length;
    const decisionCount = rows.filter((r) => r.decision_id !== null).length;
    const durations = rows
      .map((r) => r.duration_ms)
      .filter((ms): ms is number => ms !== null)
      .sort((left, right) => left - right);

    const actionCounts: Record<FinalAction, number> = {
      pass: 0,
      redact: 0,
      clarify: 0,
      block: 0,
      refuse: 0,
    };
    for (const r of rows) {
      if (r.final_action) actionCounts[r.final_action] += 1;
    }
    const actionData = ACTION_ORDER.map((a) => ({
      key: a,
      data: actionCounts[a],
    })).filter((d) => d.data > 0);

    const liveStageCounts: Record<LiveStageBucket, number> = {
      pending: 0,
      validate: 0,
      defend: 0,
      classify: 0,
      deception_inspect: 0,
      sanitize: 0,
      route: 0,
      execute: 0,
      refusal: 0,
      verify: 0,
      rehydrate: 0,
      decision_emit: 0,
      report: 0,
    };
    for (const row of rows) {
      if (!row.live) continue;
      const stage = row.stage ?? "pending";
      liveStageCounts[stage] += 1;
    }
    const liveStageData = STAGE_ORDER.map((stage) => ({
      key: stage,
      label: STAGE_LABELS[stage],
      data: liveStageCounts[stage],
    })).filter((entry) => entry.data > 0);

    const currentBandTotals: Record<RiskBand, number> = { low: 0, med: 0, high: 0 };
    for (const row of rows) {
      const band = riskBandFor(row.max_risk);
      if (band) currentBandTotals[band] += 1;
    }

    const matrixBandTotals: Record<RiskBand, number> = { low: 0, med: 0, high: 0 };
    const matrixActionCounts: Record<FinalAction, number> = {
      pass: 0,
      redact: 0,
      clarify: 0,
      block: 0,
      refuse: 0,
    };
    for (const row of matrixSourceRows) {
      const band = riskBandFor(row.max_risk);
      if (band) matrixBandTotals[band] += 1;
      if (row.final_action) matrixActionCounts[row.final_action] += 1;
    }

    const actionRiskRows = ACTION_ORDER.map((action) => {
      const cells = RISK_ORDER.map((band) => ({
        band,
        count: matrixSourceRows.filter(
          (row) => row.final_action === action && riskBandFor(row.max_risk) === band,
        ).length,
      }));
      return {
        action,
        total: matrixActionCounts[action],
        cells,
      };
    }).filter((row) => row.total > 0 || row.cells.some((cell) => cell.count > 0));

    const refusalCounts = new Map<string, number>();
    for (const row of rows) {
      if (!row.refusal_code) continue;
      refusalCounts.set(row.refusal_code, (refusalCounts.get(row.refusal_code) ?? 0) + 1);
    }
    const refusalData = [...refusalCounts.entries()]
      .map(([code, count]) => ({ code, count }))
      .sort((left, right) => right.count - left.count || left.code.localeCompare(right.code));

    // Build per-minute volume bins. Cheap UI, not statistically rigorous —
    // each bin is a one-minute bucket relative to the most-recent timestamp,
    // up to the last 30 minutes.
    const sparklineBins = 30;
    const buckets = new Array(sparklineBins).fill(0) as number[];
    if (rows.length > 0) {
      const tsList = rows.map((r) => Date.parse(r.started_at)).filter((n) => !Number.isNaN(n));
      if (tsList.length > 0) {
        const max = Math.max(...tsList);
        const minuteMs = 60_000;
        for (const t of tsList) {
          const idx = sparklineBins - 1 - Math.floor((max - t) / minuteMs);
          if (idx >= 0 && idx < sparklineBins) {
            buckets[idx] = (buckets[idx] ?? 0) + 1;
          }
        }
      }
    }
    const sparklineData = buckets.map((v, i) => ({
      key: new Date(Date.now() - (sparklineBins - 1 - i) * 60_000),
      data: v,
    }));
    const peakMinuteCount = Math.max(0, ...buckets);
    const activeMinuteCount = buckets.filter((count) => count > 0).length;
    const latestMinuteCount = buckets.at(-1) ?? 0;

    const avgDuration =
      durations.reduce((sum, durationMs) => sum + durationMs, 0) / Math.max(1, durations.length);
    const p95Duration = percentile(durations, 95);

    // FunnelChart progression: Total → Pass → Redact → Block. Each step is
    // a sub-count of the prior. Visualizes how the population funnels
    // through the guard's coarse decision tree.
    const funnelData = [
      { key: "Total", data: visibleCount },
      { key: "Pass", data: actionCounts.pass },
      { key: "Redact", data: actionCounts.redact },
      { key: "Block", data: actionCounts.block + actionCounts.refuse },
    ].filter((d) => d.data > 0);

    const funnelDetails = [
      { label: "Total", count: visibleCount },
      { label: "Pass", count: actionCounts.pass },
      { label: "Redact", count: actionCounts.redact },
      { label: "Block/refuse", count: actionCounts.block + actionCounts.refuse },
    ].map((entry) => ({
      ...entry,
      shareOfVisible: visibleCount > 0 ? entry.count / visibleCount : 0,
    }));

    const leadingLiveStage =
      liveStageData.length > 0
        ? liveStageData.reduce(
            (best, current) => {
              if (best === null) return current;
              if (current.data > best.data) return current;
              if (current.data === best.data && current.label.localeCompare(best.label) < 0) {
                return current;
              }
              return best;
            },
            null as (typeof liveStageData)[number] | null,
          )
        : null;

    const refusalTotalCount = refusalData.reduce((sum, entry) => sum + entry.count, 0);
    const refusalDetails = refusalData.map((entry) => ({
      ...entry,
      shareOfRefusals: refusalTotalCount > 0 ? entry.count / refusalTotalCount : 0,
    }));

    return {
      visibleCount,
      matchingCount,
      liveCount,
      erroredCount,
      staleLiveCount,
      decisionCount,
      actionData,
      currentBandTotals,
      matrixBandTotals,
      liveStageData,
      leadingLiveStage,
      actionRiskRows,
      refusalData: refusalDetails,
      refusalTotalCount,
      sparklineData,
      peakMinuteCount,
      activeMinuteCount,
      latestMinuteCount,
      funnelData,
      funnelDetails,
      avgDuration: Math.round(avgDuration),
      p95Duration,
      maxLiveStageCount: Math.max(1, ...liveStageData.map((entry) => entry.data)),
      maxMatrixCount: Math.max(
        1,
        ...actionRiskRows.flatMap((row) => row.cells.map((cell) => cell.count)),
      ),
      maxRefusalCount: Math.max(1, ...refusalData.map((entry) => entry.count)),
    };
  }, [matrixRows, rows, totalMatching]);

  const hasActiveMatrixFilter = activeActionFilters.length > 0 || activeRiskFilters.length > 0;

  return (
    <section className="grid grid-cols-1 gap-3 xl:grid-cols-12">
      <Card className="xl:col-span-3">
        <CardHeader
          title="Snapshot"
          subtitle={
            stats.matchingCount > stats.visibleCount
              ? `${stats.visibleCount} visible of ${stats.matchingCount} matching`
              : "visible page"
          }
        />
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
              Requests
            </div>
            <div className="text-4xl font-semibold tabular-nums">{stats.visibleCount}</div>
          </div>
          {stats.liveCount > 0 ? (
            <Badge variant="default" className="animate-pulse">
              {stats.liveCount} live
            </Badge>
          ) : (
            <Badge variant="outline">stable page</Badge>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <MiniStat label="Errored" value={stats.erroredCount} tone="destructive" />
          <MiniStat label="Stale live" value={stats.staleLiveCount} tone="warning" />
          <MiniStat
            label="P95"
            value={stats.p95Duration !== null ? `${stats.p95Duration} ms` : "—"}
            tone="default"
          />
          <MiniStat
            label="Avg"
            value={stats.avgDuration > 0 ? `${stats.avgDuration} ms` : "—"}
            tone="default"
          />
          <MiniStat label="Decisions" value={stats.decisionCount} tone="default" />
          <MiniStat
            label="High risk"
            value={stats.currentBandTotals.high}
            tone={stats.currentBandTotals.high > 0 ? "destructive" : "default"}
          />
        </div>
      </Card>

      <Card className="xl:col-span-3">
        <CardHeader title="Volume" subtitle="last 30 min · visible page" />
        <div className="h-28">
          <AreaSparklineChart data={stats.sparklineData} />
        </div>

        {stats.actionData.length > 0 ? (
          <ul className="grid gap-2 text-[10px] sm:grid-cols-2 xl:grid-cols-2">
            {stats.actionData.map((entry) => (
              <li key={entry.key}>
                <button
                  type="button"
                  onClick={() => onActionFilter?.(entry.key as FinalAction)}
                  disabled={!onActionFilter}
                  aria-pressed={activeActionFilters.includes(entry.key as FinalAction)}
                  title={onActionFilter ? `Filter table to action "${entry.key}"` : undefined}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left transition-colors hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent",
                    activeActionFilters.includes(entry.key as FinalAction) &&
                      "border-primary bg-primary/5 text-foreground",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: ACTION_COLORS[entry.key as FinalAction] }}
                    />
                    <span className="font-medium capitalize">{entry.key}</span>
                  </span>
                  <span className="tabular-nums text-muted-foreground">{entry.data}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyChartState label="No completed actions on this page." />
        )}

        <div className="grid grid-cols-3 gap-2">
          <DetailSummary label="Peak/min" value={stats.peakMinuteCount} />
          <DetailSummary
            label="Busy mins"
            value={`${stats.activeMinuteCount}/${stats.sparklineData.length}`}
          />
          <DetailSummary label="Latest min" value={stats.latestMinuteCount} />
        </div>
      </Card>

      <Card className="xl:col-span-3">
        <CardHeader
          title="Live by stage"
          subtitle={
            stats.liveCount > 0
              ? `${stats.liveCount} live across ${stats.liveStageData.length} stages`
              : "current pipeline location"
          }
        />
        {stats.liveStageData.length > 0 ? (
          <ul className="grid content-start gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {stats.liveStageData.map((entry) => (
              <li key={entry.key} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium">{entry.label}</span>
                  <Badge variant="secondary" className="tabular-nums">
                    {entry.data}
                  </Badge>
                </div>
                <MeterBar value={entry.data} max={stats.maxLiveStageCount} tone="primary" />
              </li>
            ))}
          </ul>
        ) : (
          <EmptyChartState label="No live requests on this page." />
        )}

        <div className="grid grid-cols-3 gap-2">
          <DetailSummary label="Active stages" value={stats.liveStageData.length} />
          <DetailSummary label="Frontier" value={stats.leadingLiveStage?.label ?? "—"} />
          <DetailSummary label="Stale live" value={stats.staleLiveCount} />
        </div>
      </Card>

      <Card className="xl:col-span-3">
        <CardHeader title="Funnel" subtitle="Total → Pass → Redact → Block" />
        {stats.funnelData.length > 1 ? (
          <div className="h-48">
            <FunnelChart data={stats.funnelData} series={<FunnelSeries />} />
          </div>
        ) : (
          <EmptyChartState label="Not enough outcomes to plot a funnel yet." />
        )}

        <div className="grid grid-cols-2 gap-2">
          {stats.funnelDetails.map((entry) => (
            <DetailSummary
              key={entry.label}
              label={entry.label}
              value={entry.count}
              caption={`${formatPercent(entry.shareOfVisible)} of page`}
            />
          ))}
        </div>
      </Card>

      <Card className="xl:col-span-8">
        <CardHeader
          title="Action × Risk"
          subtitle={
            hasActiveMatrixFilter
              ? "distribution stays pinned to the loaded slice"
              : "final action crossed with max risk"
          }
        />
        {stats.actionRiskRows.length > 0 ? (
          <div className="grid grid-cols-[minmax(96px,1.15fr)_repeat(3,minmax(0,1fr))] gap-2 text-xs">
            <div />
            {RISK_ORDER.map((band) => (
              <button
                key={band}
                type="button"
                onClick={() => onRiskFilter?.(band)}
                disabled={!onRiskFilter}
                aria-pressed={activeRiskFilters.includes(band)}
                title={onRiskFilter ? `Filter table to risk "${band}"` : undefined}
                className={cn(
                  "min-h-[72px] rounded-md border px-3 py-3 text-left transition-colors hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent",
                  activeRiskFilters.includes(band) && "border-primary bg-primary/5 text-foreground",
                )}
              >
                <div className="font-semibold uppercase tracking-wide">{band}</div>
                <div className="tabular-nums text-muted-foreground">
                  {stats.matrixBandTotals[band]}
                </div>
              </button>
            ))}

            {stats.actionRiskRows.map((row) => (
              <Fragment key={row.action}>
                <button
                  type="button"
                  onClick={() => onActionFilter?.(row.action)}
                  disabled={!onActionFilter}
                  aria-pressed={activeActionFilters.includes(row.action)}
                  title={onActionFilter ? `Filter table to action "${row.action}"` : undefined}
                  className={cn(
                    "min-h-[72px] rounded-md border px-3 py-3 text-left transition-colors hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent",
                    activeActionFilters.includes(row.action) &&
                      "border-primary bg-primary/5 text-foreground",
                  )}
                >
                  <div className="font-semibold capitalize">{row.action}</div>
                  <div className="tabular-nums text-muted-foreground">{row.total}</div>
                </button>

                {row.cells.map((cell) => (
                  <div
                    key={`${row.action}-${cell.band}`}
                    className="flex min-h-[72px] flex-col justify-between rounded-md border px-3 py-3"
                    style={{
                      backgroundColor:
                        cell.count > 0
                          ? tint(cell.band, cell.count / stats.maxMatrixCount)
                          : undefined,
                    }}
                  >
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {cell.band}
                    </div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {cell.count > 0 ? cell.count : "—"}
                    </div>
                  </div>
                ))}
              </Fragment>
            ))}
          </div>
        ) : (
          <EmptyChartState label="No action and risk pairs on this page yet." />
        )}
      </Card>

      <Card className="xl:col-span-4">
        <CardHeader title="Refusal codes" subtitle="ranked blockers and refusals" />
        {stats.refusalData.length > 0 ? (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {stats.refusalData.map((entry) => (
              <li key={entry.code} className="space-y-1">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-mono font-medium">{entry.code}</span>
                  <Badge variant="destructive" className="tabular-nums">
                    {entry.count}
                  </Badge>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {formatPercent(entry.shareOfRefusals)} of refusal rows
                </div>
                <MeterBar value={entry.count} max={stats.maxRefusalCount} tone="destructive" />
              </li>
            ))}
          </ul>
        ) : (
          <EmptyChartState label="No refusal codes on this page." />
        )}

        <div className="grid grid-cols-3 gap-2">
          <DetailSummary label="Unique codes" value={stats.refusalData.length} />
          <DetailSummary label="Refusal rows" value={stats.refusalTotalCount} />
          <DetailSummary
            label="Top share"
            value={stats.refusalData[0] ? formatPercent(stats.refusalData[0].shareOfRefusals) : "—"}
          />
        </div>
      </Card>
    </section>
  );
}

function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-4 rounded-md border bg-card p-4", className)}>
      {children}
    </div>
  );
}

function CardHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <h3 className="text-xs font-semibold uppercase tracking-wide">{title}</h3>
      <span className="text-[10px] text-muted-foreground">{subtitle}</span>
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: "default" | "destructive" | "warning";
}) {
  return (
    <div className="rounded-md border bg-background/60 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 text-lg font-semibold tabular-nums",
          tone === "destructive" && "text-destructive",
          tone === "warning" && "text-amber-600 dark:text-amber-400",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function DetailSummary({
  label,
  value,
  caption,
}: {
  label: string;
  value: number | string;
  caption?: string;
}) {
  return (
    <div className="rounded-md border bg-background/60 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
      {caption ? <div className="mt-0.5 text-[10px] text-muted-foreground">{caption}</div> : null}
    </div>
  );
}

function MeterBar({
  value,
  max,
  tone,
}: {
  value: number;
  max: number;
  tone: "primary" | "destructive";
}) {
  const width = `${Math.max(10, Math.round((value / Math.max(1, max)) * 100))}%`;
  return (
    <div className="h-2 overflow-hidden rounded-full bg-muted/60">
      <div
        className={cn(
          "h-full rounded-full",
          tone === "primary" ? "bg-primary/80" : "bg-destructive/80",
        )}
        style={{ width }}
      />
    </div>
  );
}

function EmptyChartState({ label }: { label: string }) {
  return (
    <div className="flex h-20 items-center justify-center text-[10px] text-muted-foreground">
      {label}
    </div>
  );
}

function riskBandFor(maxRisk: number | null): RiskBand | null {
  if (maxRisk === null) return null;
  if (maxRisk < 0.5) return "low";
  if (maxRisk < 0.85) return "med";
  return "high";
}

function isStale(summary: RequestSummary, now: number): boolean {
  if (!summary.live) return false;
  const last = Date.parse(summary.last_event_at);
  if (Number.isNaN(last)) return false;
  return now - last > CLIENT_STALE_THRESHOLD_MS;
}

function percentile(sortedValues: number[], pct: number): number | null {
  if (sortedValues.length === 0) return null;
  const index = Math.min(sortedValues.length - 1, Math.ceil((pct / 100) * sortedValues.length) - 1);
  return sortedValues[index] ?? null;
}

function tint(band: RiskBand, intensity: number): string {
  const [red, green, blue] = RISK_TINTS[band];
  const alpha = 0.12 + intensity * 0.36;
  return `rgba(${red}, ${green}, ${blue}, ${alpha.toFixed(3)})`;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
