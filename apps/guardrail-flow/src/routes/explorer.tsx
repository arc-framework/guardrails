import { useExplorerFilters } from "@/hooks/useExplorerFilters";
import { useRequestsQuery } from "@/hooks/useRequestsQuery";
import { ExplorerFilters } from "@/components/explorer/ExplorerFilters";
import { ExplorerTable } from "@/components/explorer/ExplorerTable";
import { MetricsStrip } from "@/components/explorer/MetricsStrip";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { CorsErrorBanner } from "@/components/shared/CorsErrorBanner";
import { CorsLikelyError } from "@/lib/api";

export function ExplorerRoute() {
  const filters = useExplorerFilters();
  const params = filters.toListRequestsParams();
  const query = useRequestsQuery(params);

  const hasActiveFilters =
    filters.filters.rid_prefix !== "" ||
    filters.filters.status.length > 0 ||
    filters.filters.action.length > 0 ||
    filters.filters.risk_band.length > 0 ||
    filters.filters.since !== null ||
    filters.filters.until !== null;

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <header className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">Requests</h1>
      </header>

      {query.data && query.data.items.length > 0 ? <MetricsStrip rows={query.data.items} /> : null}

      <ExplorerFilters
        filters={filters.filters}
        setFilter={filters.setFilter}
        clear={filters.clear}
      />

      {query.isError ? (
        query.error instanceof CorsLikelyError ? (
          <CorsErrorBanner error={query.error} />
        ) : (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        )
      ) : query.isLoading || !query.data ? (
        <LoadingState rows={Math.min(filters.filters.page_size, 10)} />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title="No requests match these filters"
          description="Adjust filters or send a request through the guard pipeline."
          {...(hasActiveFilters
            ? { action: { label: "Clear filters", onClick: filters.clear } }
            : {})}
        />
      ) : (
        <ExplorerTable page={query.data} onPage={filters.setPage} />
      )}
    </div>
  );
}
