/**
 * TanStack Query client setup + the SSE-event → cache-invalidation helper.
 * Cache keys follow the convention documented in
 * `specs/013-guardrailflow-dashboard/contracts/data-fetching-layer.md`:
 *
 *   ["requests", listParams]            — explorer page
 *   ["request", rid]                    — workspace manifest
 *   ["decision", rid]                   — DecisionRecord retrieval
 *   ["debug", rid, listDebugParams]     — debug page (per cursor)
 *   ["lifecycle", rid]                  — lifecycle replay
 */

import { QueryClient } from "@tanstack/react-query";
import type { LifecycleEventBase } from "@/types/api";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

/**
 * On SSE event arrival for `rid`, invalidate the workspace manifest (so
 * the resource-availability flags refresh) and append the event to the
 * lifecycle cache (so the canvas updates without a full refetch).
 *
 * Called by useFilteredSSE's onEvent callback.
 */
export function invalidateOnSseEvent(
  client: QueryClient,
  rid: string,
  event: LifecycleEventBase,
): void {
  // Append event to the lifecycle replay cache, if present. Nothing to do
  // if the cache is cold — the next read will fetch the full replay.
  client.setQueryData<
    | {
        rid: string;
        captured_at: string;
        served_from: string;
        phases: string[];
        events: LifecycleEventBase[];
      }
    | undefined
  >(["lifecycle", rid], (prev) => {
    if (!prev) return prev;
    // Skip duplicates (server may resend on Last-Event-ID reconnect).
    if (prev.events.some((e) => e.id === event.id)) return prev;
    return { ...prev, events: [...prev.events, event] };
  });

  // Invalidate the workspace manifest on terminal events so the
  // resource-availability flags refresh (decision/debug may have just
  // become available).
  if (event.event_type === "DecisionEmitted" || event.event_type === "RequestCompleted") {
    void client.invalidateQueries({ queryKey: ["request", rid] });
    void client.invalidateQueries({ queryKey: ["decision", rid] });
  }
}
