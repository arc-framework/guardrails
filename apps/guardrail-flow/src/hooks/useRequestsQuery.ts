import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ListRequestsParams } from "@/lib/api";
import type { RequestPage } from "@/types/api";

/**
 * Server-state hook for /requests. Cache key follows the documented
 * convention: ["requests", listParams]. Auto-refetches every 5 s when
 * any row in the current page is `live`, otherwise stays cold.
 */
export function useRequestsQuery(params: ListRequestsParams) {
  return useQuery<RequestPage>({
    queryKey: ["requests", params],
    queryFn: () => api.listRequests(params),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.items.some((row) => row.live) ? 5_000 : false;
    },
  });
}
