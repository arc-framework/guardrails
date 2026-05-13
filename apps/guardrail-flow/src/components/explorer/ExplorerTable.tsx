import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { FinalAction, RequestPage, RiskBand } from "@/types/api";
import type { ExplorerRowModel } from "@/types/workflow";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { projectRow } from "./explorer-row-model";

export interface ExplorerTableProps {
  page: RequestPage;
  onPage: (next: number) => void;
  onPageSizeChange?: (next: number) => void;
  onActionFilter?: (action: FinalAction) => void;
  onRiskFilter?: (band: RiskBand) => void;
}

type DensityMode = "compact" | "comfortable";
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

function actionVariant(action: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (action === "block" || action === "refuse") return "destructive";
  if (action === "redact" || action === "clarify") return "secondary";
  if (action === "pass") return "outline";
  return "outline";
}

function riskVariant(band: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (band === "high") return "destructive";
  if (band === "med") return "secondary";
  return "outline";
}

export function ExplorerTable({
  page,
  onPage,
  onPageSizeChange,
  onActionFilter,
  onRiskFilter,
}: ExplorerTableProps) {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([{ id: "timing", desc: true }]);
  const [density, setDensity] = useState<DensityMode>("comfortable");
  const isCompact = density === "compact";

  const data = useMemo(() => page.items.map(projectRow), [page.items]);

  const columns = useMemo<ColumnDef<ExplorerRowModel>[]>(
    () => [
      {
        id: "request",
        accessorFn: (row) => row.summary.rid,
        header: "Request",
        enableSorting: true,
        cell: ({ row }) => {
          const rid = row.original.summary.rid;
          return (
            <div
              className={cn(
                "flex min-w-0 items-center gap-2 overflow-hidden font-mono text-xs",
                isCompact ? "max-w-[180px]" : "max-w-[270px]",
              )}
            >
              <div className="inline-flex shrink-0 items-center gap-2">
                {row.original.staleBadge ? (
                  <span
                    className="text-amber-600 dark:text-amber-400"
                    aria-label="stale (last event > 30 minutes ago)"
                    title="Live row hasn't received an event in over 30 minutes — likely stuck. Backend sweeper should resolve shortly."
                  >
                    ⚠
                  </span>
                ) : row.original.liveBadge ? (
                  <span
                    className={cn("mt-0.5 h-2 w-2 animate-pulse rounded-full bg-emerald-500")}
                    aria-label="live"
                  />
                ) : null}
              </div>
              <span className="truncate">{rid}</span>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {isCompact
                  ? relativeAge(row.original.summary.last_event_at)
                  : `last ${relativeAge(row.original.summary.last_event_at)}`}
              </span>
            </div>
          );
        },
      },
      {
        id: "pipeline",
        accessorFn: (row) => `${row.summary.status}-${row.stageDisplay}`,
        header: "Pipeline",
        enableSorting: false,
        cell: ({ row }) => {
          const summary = row.original.summary;
          return (
            <div className="flex min-w-0 items-center gap-1.5 overflow-hidden text-xs">
              <div className="flex shrink-0 items-center gap-1.5">
                <Badge variant={summary.live ? "default" : "outline"}>{summary.status}</Badge>
                <span className="font-medium text-foreground">{row.original.stageDisplay}</span>
                {row.original.staleBadge ? (
                  <Badge variant="secondary" className="text-amber-700 dark:text-amber-300">
                    stale live
                  </Badge>
                ) : null}
              </div>
              {!isCompact ? (
                <span className="truncate text-[11px] text-muted-foreground">
                  {summary.live ? "active in pipeline" : "completed stage recorded"}
                </span>
              ) : null}
            </div>
          );
        },
      },
      {
        id: "outcome",
        accessorFn: (row) => row.summary.final_action ?? "",
        header: "Outcome",
        enableSorting: true,
        cell: ({ row }) => {
          const summary = row.original.summary;
          const rid = summary.rid;
          const detailItems = [
            summary.refusal_code,
            summary.decision_id ? truncateMiddle(summary.decision_id, isCompact ? 12 : 20) : null,
            summary.max_risk !== null ? `max ${summary.max_risk.toFixed(2)}` : null,
          ].filter((value): value is string => Boolean(value));

          return (
            <div
              className={cn(
                "flex min-w-0 items-center gap-1.5 overflow-hidden",
                isCompact ? "max-w-[210px]" : "max-w-[320px]",
              )}
            >
              <div className="flex shrink-0 items-center gap-1.5">
                {summary.final_action ? (
                  <button
                    type="button"
                    aria-label={`Show only ${summary.final_action} action from ${rid}`}
                    disabled={!onActionFilter}
                    onClick={() => onActionFilter?.(summary.final_action as FinalAction)}
                    className="inline-flex disabled:cursor-default"
                  >
                    <Badge variant={actionVariant(summary.final_action)}>
                      {summary.final_action}
                    </Badge>
                  </button>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}

                {row.original.riskBand ? (
                  <button
                    type="button"
                    aria-label={`Show only ${row.original.riskBand} risk from ${rid}`}
                    disabled={!onRiskFilter}
                    onClick={() => onRiskFilter?.(row.original.riskBand as RiskBand)}
                    className="inline-flex disabled:cursor-default"
                  >
                    <Badge variant={riskVariant(row.original.riskBand)}>
                      {row.original.riskBand}
                    </Badge>
                  </button>
                ) : null}
              </div>
              {detailItems.length > 0 ? (
                <div className="flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
                  {detailItems.map((item, index) => (
                    <span key={item} className="flex min-w-0 items-center gap-1">
                      {index > 0 ? (
                        <span className="shrink-0 text-muted-foreground/70">·</span>
                      ) : null}
                      <span className="truncate">{item}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <div className="truncate text-[11px] text-muted-foreground">
                  no decision payload recorded
                </div>
              )}
            </div>
          );
        },
      },
      {
        id: "timing",
        accessorFn: (row) => row.summary.started_at,
        header: "Timing",
        enableSorting: true,
        cell: ({ row }) => {
          const summary = row.original.summary;
          return (
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span className="font-mono text-xs text-foreground">
                {row.original.durationDisplay}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {isCompact ? relativeAge(summary.started_at) : formatTimestamp(summary.started_at)}
              </span>
            </div>
          );
        },
      },
      {
        id: "actions",
        header: "Workspace",
        enableSorting: false,
        cell: ({ row }) => {
          const rid = row.original.summary.rid;
          return (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn("px-2 text-xs", isCompact ? "h-7" : "h-7")}
              aria-label={`Open workspace for ${rid}`}
              onClick={() => navigate(`/requests/${encodeURIComponent(rid)}`)}
            >
              Open
            </Button>
          );
        },
      },
    ],
    [isCompact, navigate, onActionFilter, onRiskFilter],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const startIdx = (page.page - 1) * page.page_size + 1;
  const endIdx = Math.min(startIdx + page.items.length - 1, page.total);
  const totalPages = Math.max(1, Math.ceil(page.total / page.page_size));

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-card px-3 py-2.5 shadow-sm">
        <div className="space-y-1">
          <div className="text-sm font-semibold">Request console</div>
          <p className="text-xs text-muted-foreground">
            Core request, pipeline, and outcome details stay in the row, with workspace drill-down
            one click away.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Density</span>
          <Button
            type="button"
            variant={density === "compact" ? "default" : "outline"}
            size="sm"
            aria-pressed={density === "compact"}
            onClick={() => setDensity("compact")}
          >
            Compact
          </Button>
          <Button
            type="button"
            variant={density === "comfortable" ? "default" : "outline"}
            size="sm"
            aria-pressed={density === "comfortable"}
            onClick={() => setDensity("comfortable")}
          >
            Comfortable
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border bg-card shadow-sm">
        <Table className="min-w-[1020px] border-separate border-spacing-0">
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="hover:bg-transparent">
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const isSorted = header.column.getIsSorted();
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        headerCellClass(header.column.id, density),
                        isCompact ? "h-8 px-2 text-[11px]" : "h-10 px-3 text-xs",
                      )}
                    >
                      {canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className={cn(
                            "flex items-center gap-1 text-left font-semibold tracking-wide text-muted-foreground hover:text-foreground",
                            isCompact ? "text-[11px]" : "text-xs",
                          )}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span aria-hidden className="text-[10px] opacity-60">
                            {isSorted === "asc" ? "↑" : isSorted === "desc" ? "↓" : "↕"}
                          </span>
                        </button>
                      ) : (
                        <span className="text-xs font-semibold tracking-wide text-muted-foreground">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-accent/20"
                data-state={row.original.summary.live ? "live" : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      bodyCellClass(cell.column.id, density),
                      isCompact ? "px-2 py-1.5 text-xs" : "px-3 py-2 text-xs",
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-3">
          {page.total === 0 ? "No matching requests" : `${startIdx}–${endIdx} of ${page.total}`}
          {page.total > 0 ? (
            <span>
              page {page.page} of {totalPages}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {onPageSizeChange ? (
            <div className="flex items-center gap-1 rounded-md border bg-background p-1">
              <span className="px-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                Rows
              </span>
              {PAGE_SIZE_OPTIONS.map((size) => (
                <Button
                  key={size}
                  type="button"
                  variant={page.page_size === size ? "default" : "ghost"}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  aria-pressed={page.page_size === size}
                  aria-label={`Show ${size} rows per page`}
                  onClick={() => onPageSizeChange(size)}
                >
                  {size}
                </Button>
              ))}
            </div>
          ) : null}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page.page <= 1}
              onClick={() => onPage(page.page - 1)}
            >
              Previous
            </Button>
            <span className="px-2">page {page.page}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={!page.has_more}
              onClick={() => onPage(page.page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function headerCellClass(columnId: string, density: DensityMode): string {
  const compact = density === "compact";
  return cn(
    "sticky top-0 z-20 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90",
    columnId === "request" &&
      cn("left-0 z-30", compact ? "w-[190px] min-w-[190px]" : "w-[270px] min-w-[270px]"),
    columnId === "pipeline" && cn(compact ? "w-[150px] min-w-[150px]" : "w-[210px] min-w-[210px]"),
    columnId === "outcome" && cn(compact ? "w-[220px] min-w-[220px]" : "w-[340px] min-w-[340px]"),
    columnId === "timing" && cn(compact ? "w-[110px] min-w-[110px]" : "w-[190px] min-w-[190px]"),
    columnId === "actions" && "right-0 w-[94px] min-w-[94px] text-right z-30",
  );
}

function bodyCellClass(columnId: string, density: DensityMode): string {
  const compact = density === "compact";
  return cn(
    columnId === "request" && "sticky left-0 z-10 bg-card align-middle",
    columnId === "pipeline" && "align-middle whitespace-nowrap",
    columnId === "outcome" && "align-middle",
    columnId === "timing" && cn("whitespace-nowrap align-middle", compact && "text-[11px]"),
    columnId === "actions" && "sticky right-0 z-10 bg-card text-right align-middle",
  );
}

function truncateMiddle(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  const head = Math.ceil((maxLength - 1) / 2);
  const tail = Math.floor((maxLength - 1) / 2);
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function formatTimestamp(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString();
}

function relativeAge(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "unknown";
  const diffMs = Math.max(0, Date.now() - parsed);
  const diffMinutes = Math.round(diffMs / 60_000);
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}
