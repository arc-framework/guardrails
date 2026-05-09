import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ListRequestsParams } from "@/lib/api";
import type { FinalAction, RequestStatus, RiskBand } from "@/types/api";

const VALID_STATUS: RequestStatus[] = ["live", "completed", "errored"];
const VALID_ACTION: FinalAction[] = ["pass", "block", "redact", "clarify", "refuse"];
const VALID_RISK: RiskBand[] = ["low", "med", "high"];

function parseEnumList<T extends string>(raw: string[] | null, valid: T[]): T[] {
  if (!raw) return [];
  return raw.filter((v): v is T => (valid as string[]).includes(v));
}

export interface ExplorerFiltersValue {
  page: number;
  page_size: number;
  since: string | null;
  until: string | null;
  status: RequestStatus[];
  action: FinalAction[];
  risk_band: RiskBand[];
  rid_prefix: string;
}

export interface UseExplorerFiltersReturn {
  filters: ExplorerFiltersValue;
  toListRequestsParams: () => ListRequestsParams;
  setFilter: <K extends keyof ExplorerFiltersValue>(key: K, value: ExplorerFiltersValue[K]) => void;
  setPage: (page: number) => void;
  clear: () => void;
}

export function useExplorerFilters(): UseExplorerFiltersReturn {
  const [params, setParams] = useSearchParams();

  const filters = useMemo<ExplorerFiltersValue>(() => {
    const page = Number.parseInt(params.get("page") ?? "1", 10);
    const pageSize = Number.parseInt(params.get("page_size") ?? "50", 10);
    return {
      page: Number.isNaN(page) || page < 1 ? 1 : page,
      page_size: Number.isNaN(pageSize) || pageSize < 1 ? 50 : pageSize,
      since: params.get("since"),
      until: params.get("until"),
      status: parseEnumList(params.getAll("status"), VALID_STATUS),
      action: parseEnumList(params.getAll("action"), VALID_ACTION),
      risk_band: parseEnumList(params.getAll("risk_band"), VALID_RISK),
      rid_prefix: params.get("rid_prefix") ?? "",
    };
  }, [params]);

  const toListRequestsParams = useCallback((): ListRequestsParams => {
    return {
      page: filters.page,
      page_size: filters.page_size,
      ...(filters.since ? { since: filters.since } : {}),
      ...(filters.until ? { until: filters.until } : {}),
      ...(filters.status.length > 0 ? { status: filters.status } : {}),
      ...(filters.action.length > 0 ? { action: filters.action } : {}),
      ...(filters.risk_band.length > 0 ? { risk_band: filters.risk_band } : {}),
      ...(filters.rid_prefix ? { rid_prefix: filters.rid_prefix } : {}),
    };
  }, [filters]);

  const setFilter = useCallback<UseExplorerFiltersReturn["setFilter"]>(
    (key, value) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        // Reset page when any filter (except page itself) changes.
        if (key !== "page") next.delete("page");
        if (Array.isArray(value)) {
          next.delete(key);
          for (const v of value) next.append(key, String(v));
        } else if (value === null || value === "" || value === undefined) {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
        return next;
      });
    },
    [setParams],
  );

  const setPage = useCallback((page: number) => setFilter("page", page), [setFilter]);

  const clear = useCallback(() => setParams(new URLSearchParams()), [setParams]);

  return { filters, toListRequestsParams, setFilter, setPage, clear };
}
