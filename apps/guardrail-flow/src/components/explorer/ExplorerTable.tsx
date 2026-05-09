import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import type { RequestPage } from "@/types/api";
import { projectRow } from "./explorer-row-model";
import { ExplorerRow } from "./ExplorerRow";

export interface ExplorerTableProps {
  page: RequestPage;
  onPage: (next: number) => void;
}

export function ExplorerTable({ page, onPage }: ExplorerTableProps) {
  const navigate = useNavigate();
  const rows = page.items.map(projectRow);

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
            <TableRow>
              <TableHead>rid</TableHead>
              <TableHead>status</TableHead>
              <TableHead>action</TableHead>
              <TableHead>risk</TableHead>
              <TableHead>stage</TableHead>
              <TableHead>duration</TableHead>
              <TableHead>started</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <ExplorerRow key={row.summary.rid} row={row} onClick={handleRowClick} />
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
