import { useMemo } from "react";
import { PieChart, PieArcSeries, AreaSparklineChart } from "reaviz";
import { Badge } from "@/components/ui/badge";
import type { FinalAction, RequestSummary } from "@/types/api";

export interface MetricsStripProps {
  rows: RequestSummary[];
}

const ACTION_ORDER: FinalAction[] = ["pass", "redact", "clarify", "block", "refuse"];
const ACTION_COLORS: Record<FinalAction, string> = {
  pass: "#10b981", // emerald
  redact: "#f59e0b", // amber
  clarify: "#3b82f6", // blue
  block: "#ef4444", // red
  refuse: "#dc2626", // dark red
};

const BAND_COLORS: Record<"low" | "med" | "high", string> = {
  low: "#10b981",
  med: "#f59e0b",
  high: "#ef4444",
};

export function MetricsStrip({ rows }: MetricsStripProps) {
  const stats = useMemo(() => {
    const total = rows.length;
    const liveCount = rows.filter((r) => r.live).length;
    const erroredCount = rows.filter((r) => r.status === "errored").length;

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

    const bandMutable: Record<"low" | "med" | "high", number> = { low: 0, med: 0, high: 0 };
    for (const r of rows) {
      if (r.max_risk === null) continue;
      if (r.max_risk < 0.5) bandMutable.low += 1;
      else if (r.max_risk < 0.85) bandMutable.med += 1;
      else bandMutable.high += 1;
    }
    const bandData = (["low", "med", "high"] as const)
      .map((k) => ({ key: k, data: bandMutable[k] }))
      .filter((d) => d.data > 0);

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

    const avgDuration =
      rows.filter((r) => r.duration_ms !== null).reduce((s, r) => s + (r.duration_ms ?? 0), 0) /
      Math.max(1, rows.filter((r) => r.duration_ms !== null).length);

    return {
      total,
      liveCount,
      erroredCount,
      actionData,
      bandData,
      sparklineData,
      avgDuration: Math.round(avgDuration),
    };
  }, [rows]);

  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card>
        <CardHeader title="Total" subtitle="visible page" />
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-semibold tabular-nums">{stats.total}</span>
          <div className="flex flex-col gap-0.5 text-xs">
            {stats.liveCount > 0 ? (
              <Badge variant="default" className="animate-pulse">
                {stats.liveCount} live
              </Badge>
            ) : null}
            {stats.erroredCount > 0 ? (
              <Badge variant="destructive">{stats.erroredCount} errored</Badge>
            ) : null}
            <span className="text-muted-foreground">
              {stats.avgDuration > 0 ? `avg ${stats.avgDuration} ms` : "—"}
            </span>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Volume" subtitle="last 30 min" />
        <div className="h-16">
          <AreaSparklineChart data={stats.sparklineData} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Actions" subtitle="final outcome" />
        {stats.actionData.length > 0 ? (
          <div className="flex items-center gap-3">
            <div className="h-20 w-20 shrink-0">
              <PieChart
                data={stats.actionData}
                series={
                  <PieArcSeries
                    doughnut
                    colorScheme={stats.actionData.map((d) => ACTION_COLORS[d.key as FinalAction])}
                    label={null}
                  />
                }
              />
            </div>
            <ul className="flex flex-wrap gap-1 text-[10px]">
              {stats.actionData.map((d) => (
                <li key={d.key} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: ACTION_COLORS[d.key as FinalAction] }}
                  />
                  <span className="font-medium">{d.key}</span>
                  <span className="text-muted-foreground">×{d.data}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <EmptyChartState />
        )}
      </Card>

      <Card>
        <CardHeader title="Risk" subtitle="max risk band" />
        {stats.bandData.length > 0 ? (
          <div className="flex items-center gap-3">
            <div className="h-20 w-20 shrink-0">
              <PieChart
                data={stats.bandData}
                series={
                  <PieArcSeries
                    doughnut
                    colorScheme={stats.bandData.map(
                      (d) => BAND_COLORS[d.key as "low" | "med" | "high"],
                    )}
                    label={null}
                  />
                }
              />
            </div>
            <ul className="flex flex-wrap gap-1 text-[10px]">
              {stats.bandData.map((d) => (
                <li key={d.key} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: BAND_COLORS[d.key as "low" | "med" | "high"] }}
                  />
                  <span className="font-medium uppercase">{d.key}</span>
                  <span className="text-muted-foreground">×{d.data}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <EmptyChartState />
        )}
      </Card>
    </section>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-2 rounded-md border bg-card p-3">{children}</div>;
}

function CardHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <h3 className="text-xs font-semibold uppercase tracking-wide">{title}</h3>
      <span className="text-[10px] text-muted-foreground">{subtitle}</span>
    </div>
  );
}

function EmptyChartState() {
  return (
    <div className="flex h-20 items-center justify-center text-[10px] text-muted-foreground">
      No data yet
    </div>
  );
}
