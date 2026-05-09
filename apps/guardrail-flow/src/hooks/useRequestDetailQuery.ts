import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RequestWorkspaceManifest } from "@/types/api";

/**
 * Server-state hook for /requests/{rid}. Cache key ["request", rid].
 * Refetched lazily on SSE-driven invalidation (see query-client.ts).
 */
export function useRequestDetailQuery(rid: string | undefined) {
  return useQuery<RequestWorkspaceManifest>({
    queryKey: ["request", rid],
    queryFn: () => {
      if (!rid) throw new Error("rid required");
      return api.getRequestDetail(rid);
    },
    enabled: !!rid,
  });
}
