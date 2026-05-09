import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
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
import type { ExplorerRowModel } from "@/types/workflow";
import type { RequestPage } from "@/types/api";
import { projectRow } from "./explorer-row-model";

export interface ExplorerTableProps {
  page: RequestPage;
  onPage: (next: number) => void;
}

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

const RISK_BAND_ORDER: Record<string, number> = { low: 0, med: 1, high: 2 };

const columns: ColumnDef<ExplorerRowModel>[] = [
  {
    id: "rid",
    accessorFn: (r) => r.summary.rid,
    header: "rid",
    enableSorting: true,
    cell: ({ row }) => (
      <span className="inline-flex items-center gap-2 font-mono text-xs">
        {row.original.liveBadge ? (
          <span
            className={cn("h-2 w-2 animate-pulse rounded-full bg-emerald-500")}
            aria-label="live"
          />
        ) : null}
        {row.original.summary.rid}
      </span>
    ),
  },
  {
    id: "status",
    accessorFn: (r) => r.summary.status,
    header: "status",
    enableSorting: true,
    cell: ({ row }) => (
      <Badge variant={row.original.summary.live ? "default" : "outline"}>
        {row.original.summary.status}
      </Badge>
    ),
  },
  {
    id: "action",
    accessorFn: (r) => r.summary.final_action ?? "",
    header: "action",
    enableSorting: true,
    cell: ({ row }) =>
      row.original.summary.final_action ? (
        <Badge variant={actionVariant(row.original.summary.final_action)}>
          {row.original.summary.final_action}
        </Badge>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    id: "risk",
    accessorFn: (r) => (r.riskBand ? (RISK_BAND_ORDER[r.riskBand] ?? -1) : -1),
    header: "risk",
    enableSorting: true,
    cell: ({ row }) =>
      row.original.riskBand ? (
        <Badge variant={riskVariant(row.original.riskBand)}>{row.original.riskBand}</Badge>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    id: "stage",
    accessorFn: (r) => r.stageDisplay,
    header: "stage",
    enableSorting: false,
    cell: ({ row }) => <span className="text-muted-foreground">{row.original.stageDisplay}</span>,
  },
  {
    id: "duration",
    accessorFn: (r) => r.summary.duration_ms ?? -1,
    header: "duration",
    enableSorting: true,
    cell: ({ row }) => <span className="font-mono text-xs">{row.original.durationDisplay}</span>,
  },
  {
    id: "started",
    accessorFn: (r) => r.summary.started_at,
    header: "started",
    enableSorting: true,
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground">
        {new Date(row.original.summary.started_at).toLocaleString()}
      </span>
    ),
  },
];

export function ExplorerTable({ page, onPage }: ExplorerTableProps) {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([{ id: "started", desc: true }]);

  const data = useMemo(() => page.items.map(projectRow), [page.items]);

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

  const handleRowClick = (rid: string) => {
    navigate(`/requests/${encodeURIComponent(rid)}`);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const isSorted = header.column.getIsSorted();
                  return (
                    <TableHead key={header.id}>
                      {canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="flex items-center gap-1 text-left text-xs font-medium hover:text-foreground"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span aria-hidden className="text-[10px] opacity-60">
                            {isSorted === "asc" ? "↑" : isSorted === "desc" ? "↓" : "↕"}
                          </span>
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
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
                onClick={() => handleRowClick(row.original.summary.rid)}
                className="cursor-pointer hover:bg-accent/50"
                data-state={row.original.summary.live ? "live" : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div>
          {page.total === 0 ? "No matching requests" : `${startIdx}–${endIdx} of ${page.total}`}
        </div>
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
  );
}
