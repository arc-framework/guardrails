/**
 * Filtered SSE wrapper around @microsoft/fetch-event-source. Subscribes
 * to `GET /events?rid=<rid>` and emits typed callbacks for `lifecycle` /
 * `terminated` / errors. Tracks `lastEventId` for reconnect via the
 * Last-Event-ID header.
 *
 * The hook in `src/hooks/useFilteredSSE.ts` composes this module with the
 * three-trigger close logic to deliver the FR-009 contract.
 */

import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { LifecycleEventBase, TerminatedSentinel } from "@/types/api";

export interface FilteredEventsOptions {
  baseUrl: string;
  rid: string;
  authorization?: string | null;
  lastEventId?: string | null;
  signal: AbortSignal;
  onEvent: (event: LifecycleEventBase) => void;
  onTerminated: (sentinel: TerminatedSentinel) => void;
  onError: (error: Error) => void;
  onOpen?: () => void;
}

class RetriableError extends Error {}
class FatalError extends Error {}

function parseLifecycle(data: string): LifecycleEventBase | null {
  try {
    const parsed = JSON.parse(data);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof parsed.id === "string" &&
      typeof parsed.seq === "number" &&
      typeof parsed.rid === "string" &&
      typeof parsed.event_type === "string"
    ) {
      return parsed as LifecycleEventBase;
    }
    return null;
  } catch {
    return null;
  }
}

function parseTerminated(data: string): TerminatedSentinel | null {
  try {
    const parsed = JSON.parse(data);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof parsed.rid === "string" &&
      ["completed", "already_completed", "errored"].includes(parsed.reason)
    ) {
      return parsed as TerminatedSentinel;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Open a filtered SSE connection. Resolves when the server closes the
 * stream cleanly (terminated sentinel) or rejects via signal abort. The
 * caller owns the AbortController.
 */
export async function openFilteredEvents(opts: FilteredEventsOptions): Promise<void> {
  const url = `${opts.baseUrl}/events?rid=${encodeURIComponent(opts.rid)}`;
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
  };
  if (opts.lastEventId) {
    headers["Last-Event-ID"] = opts.lastEventId;
  }
  if (opts.authorization) {
    headers["Authorization"] = opts.authorization;
  }
  await fetchEventSource(url, {
    method: "GET",
    headers,
    signal: opts.signal,
    credentials: "omit",
    openWhenHidden: false,
    async onopen(response) {
      if (response.ok) {
        opts.onOpen?.();
        return;
      }
      // 4xx is fatal; 5xx is retried by the library.
      if (response.status >= 400 && response.status < 500) {
        throw new FatalError(`SSE open failed: ${response.status} ${response.statusText}`);
      }
      throw new RetriableError();
    },
    onmessage(msg) {
      if (msg.event === "terminated") {
        const sentinel = parseTerminated(msg.data);
        if (sentinel) {
          opts.onTerminated(sentinel);
        } else {
          opts.onError(new Error(`malformed terminated payload: ${msg.data}`));
        }
        return;
      }
      if (msg.event === "lifecycle") {
        const ev = parseLifecycle(msg.data);
        if (ev) {
          opts.onEvent(ev);
        } else {
          opts.onError(new Error(`malformed lifecycle payload: ${msg.data}`));
        }
        return;
      }
      // Unknown event type — ignore (forward-compatibility).
    },
    onerror(error) {
      if (error instanceof FatalError) {
        opts.onError(error);
        throw error;
      }
      // Retriable; let the library back-off and retry.
      opts.onError(error instanceof Error ? error : new Error(String(error)));
    },
    onclose() {
      // Clean close — let the caller's onTerminated handle the state
      // transition. If the stream closed without a sentinel, fall through.
    },
  });
}
