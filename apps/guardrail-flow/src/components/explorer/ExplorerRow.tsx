import { Badge } from "@/components/ui/badge";
import { TableCell, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { ExplorerRowModel } from "@/types/workflow";

export interface ExplorerRowProps {
  row: ExplorerRowModel;
  onClick: (rid: string) => void;
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

export function ExplorerRow({ row, onClick }: ExplorerRowProps) {
  const { summary } = row;
  return (
    <TableRow
      onClick={() => onClick(summary.rid)}
      className="cursor-pointer hover:bg-accent/50"
      data-state={summary.live ? "live" : undefined}
    >
      <TableCell className="font-mono text-xs">
        <span className="inline-flex items-center gap-2">
          {row.liveBadge ? (
            <span
              className={cn("h-2 w-2 animate-pulse rounded-full bg-green-500")}
              aria-label="live"
            />
          ) : null}
          {summary.rid}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant={summary.live ? "default" : "outline"}>{summary.status}</Badge>
      </TableCell>
      <TableCell>
        {summary.final_action ? (
          <Badge variant={actionVariant(summary.final_action)}>{summary.final_action}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {row.riskBand ? (
          <Badge variant={riskVariant(row.riskBand)}>{row.riskBand}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">{row.stageDisplay}</TableCell>
      <TableCell className="font-mono text-xs">{row.durationDisplay}</TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {new Date(summary.started_at).toLocaleString()}
      </TableCell>
    </TableRow>
  );
}
