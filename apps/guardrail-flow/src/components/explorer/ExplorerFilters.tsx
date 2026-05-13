import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { FinalAction, RequestStatus, RiskBand } from "@/types/api";
import type { UseExplorerFiltersReturn } from "@/hooks/useExplorerFilters";

const STATUS_OPTIONS: RequestStatus[] = ["live", "completed", "errored"];
const ACTION_OPTIONS: FinalAction[] = ["pass", "block", "redact", "clarify", "refuse"];
const RISK_OPTIONS: RiskBand[] = ["low", "med", "high"];

function MultiSelectChips<T extends string>({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: readonly T[];
  selected: T[];
  onChange: (next: T[]) => void;
}) {
  const toggle = (value: T) => {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  };
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="flex flex-wrap gap-1">
        {options.map((opt) => {
          const active = selected.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className="rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <Badge variant={active ? "default" : "outline"}>{opt}</Badge>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface ExplorerFiltersProps {
  filters: UseExplorerFiltersReturn["filters"];
  setFilter: UseExplorerFiltersReturn["setFilter"];
  clear: UseExplorerFiltersReturn["clear"];
}

export function ExplorerFilters({ filters, setFilter, clear }: ExplorerFiltersProps) {
  const hasAny =
    filters.since !== null ||
    filters.until !== null ||
    filters.status.length > 0 ||
    filters.action.length > 0 ||
    filters.risk_band.length > 0 ||
    filters.rid_prefix !== "";

  return (
    <div className="flex flex-col gap-3 rounded-md border bg-card p-3 shadow-sm">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="rid-prefix" className="text-xs font-medium text-muted-foreground">
            RID Prefix
          </label>
          <Input
            id="rid-prefix"
            value={filters.rid_prefix}
            onChange={(e) => setFilter("rid_prefix", e.target.value)}
            placeholder="01J..."
            className="h-8"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="since" className="text-xs font-medium text-muted-foreground">
            Since (ISO 8601)
          </label>
          <Input
            id="since"
            value={filters.since ?? ""}
            onChange={(e) => setFilter("since", e.target.value === "" ? null : e.target.value)}
            placeholder="2026-05-09T00:00:00Z"
            className="h-8"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="until" className="text-xs font-medium text-muted-foreground">
            Until (ISO 8601)
          </label>
          <Input
            id="until"
            value={filters.until ?? ""}
            onChange={(e) => setFilter("until", e.target.value === "" ? null : e.target.value)}
            placeholder="2026-05-10T00:00:00Z"
            className="h-8"
          />
        </div>
        <div className="flex items-end justify-end">
          {hasAny ? (
            <Button variant="outline" size="sm" onClick={clear}>
              Clear filters
            </Button>
          ) : null}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MultiSelectChips
          label="Status"
          options={STATUS_OPTIONS}
          selected={filters.status}
          onChange={(v) => setFilter("status", v)}
        />
        <MultiSelectChips
          label="Action"
          options={ACTION_OPTIONS}
          selected={filters.action}
          onChange={(v) => setFilter("action", v)}
        />
        <MultiSelectChips
          label="Risk Band"
          options={RISK_OPTIONS}
          selected={filters.risk_band}
          onChange={(v) => setFilter("risk_band", v)}
        />
      </div>
    </div>
  );
}
