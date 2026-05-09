import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api";
import type { RequestDecisionEnvelope } from "@/types/api";

/**
 * Server-state hook for /requests/{rid}/decision. Cache key ["decision", rid].
 *
 * "Decision not captured" is a normal terminal state for some lifecycles, so
 * the hook treats `decision_not_captured` as a successful empty result rather
 * than an error.
 */
export function useDecisionQuery(rid: string | undefined, enabled = true) {
  return useQuery<RequestDecisionEnvelope | null>({
    queryKey: ["decision", rid],
    queryFn: async () => {
      if (!rid) throw new Error("rid required");
      try {
        return await api.getRequestDecision(rid);
      } catch (err) {
        if (err instanceof ApiError && err.code === "decision_not_captured") {
          return null;
        }
        throw err;
      }
    },
    enabled: !!rid && enabled,
  });
}
