import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api";
import type { RequestDebugPage } from "@/types/api";

const DEFAULT_PAGE_SIZE = 50;

export interface UseDebugQueryOptions {
  pageSize?: number;
  enabled?: boolean;
}

/**
 * Cursor-paginated hook for /requests/{rid}/debug. Cache key ["debug", rid, pageSize].
 *
 * Returns an InfiniteQuery so the LogsTab can call `fetchNextPage()` when the
 * scroll-to-bottom sentinel intersects. "Debug not captured" is a normal
 * terminal state, so the hook returns an empty page rather than erroring.
 */
export function useDebugQuery(rid: string | undefined, opts: UseDebugQueryOptions = {}) {
  const pageSize = opts.pageSize ?? DEFAULT_PAGE_SIZE;
  const enabled = opts.enabled ?? true;

  return useInfiniteQuery<RequestDebugPage>({
    queryKey: ["debug", rid, pageSize],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      if (!rid) throw new Error("rid required");
      try {
        return await api.getRequestDebug(rid, {
          page_size: pageSize,
          cursor: typeof pageParam === "string" ? pageParam : undefined,
        });
      } catch (err) {
        if (err instanceof ApiError && err.code === "debug_not_captured") {
          return {
            rid,
            items: [],
            page_size: pageSize,
            next_cursor: null,
            has_more: false,
          };
        }
        throw err;
      }
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!rid && enabled,
  });
}
