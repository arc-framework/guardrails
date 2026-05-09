import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { LifecycleReplay } from "@/types/api";

/**
 * Server-state hook for /lifecycle/{rid}. Cache key ["lifecycle", rid].
 * Live SSE events append to this cache incrementally via
 * invalidateOnSseEvent() rather than triggering a full refetch.
 */
export function useLifecycleQuery(rid: string | undefined) {
  return useQuery<LifecycleReplay>({
    queryKey: ["lifecycle", rid],
    queryFn: () => {
      if (!rid) throw new Error("rid required");
      return api.getLifecycleReplay(rid);
    },
    enabled: !!rid,
  });
}
