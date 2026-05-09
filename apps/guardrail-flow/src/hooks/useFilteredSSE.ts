/**
 * React hook for filtered live SSE on `GET /events?rid=<rid>`. Composes
 * `openFilteredEvents` (the @microsoft/fetch-event-source wrapper) with
 * `createCloseTriggers` (the three-trigger close logic) per the
 * FR-009 contract.
 *
 * Usage:
 *
 *   const { status, lastEventId } = useFilteredSSE({
 *     rid,
 *     enabled: manifest.summary.live === true,
 *     onEvent: (event) => invalidateLifecycleCache(event),
 *     onTerminated: (reason) => setRequestTerminal(reason),
 *     onError: (error) => showCorsBanner(error),
 *   });
 *
 * The hook auto-resubscribes when the tab returns from a 60 s hidden
 * throttle, using the last known event id as the Last-Event-ID header.
 */

import { useEffect, useRef, useState } from "react";
import type { LifecycleEventBase, TerminatedSentinel } from "@/types/api";
import { env } from "@/lib/env";
import { openFilteredEvents } from "@/lib/sse/filtered-events";
import { createCloseTriggers } from "@/lib/sse/close-triggers";
import { onVisibilityChange, isHidden } from "@/lib/sse/visibility";

export type SseStatus = "idle" | "connecting" | "live" | "throttled" | "terminated" | "error";

export interface UseFilteredSSEOptions {
  rid: string;
  enabled: boolean;
  onEvent: (event: LifecycleEventBase) => void;
  onTerminated: (reason: TerminatedSentinel["reason"]) => void;
  onError: (error: Error) => void;
}

export interface UseFilteredSSEReturn {
  status: SseStatus;
  lastEventId: string | null;
}

export function useFilteredSSE(opts: UseFilteredSSEOptions): UseFilteredSSEReturn {
  const [status, setStatus] = useState<SseStatus>("idle");
  const lastEventIdRef = useRef<string | null>(null);
  const callbacksRef = useRef(opts);
  callbacksRef.current = opts;

  useEffect(() => {
    if (!opts.enabled) {
      setStatus("idle");
      return undefined;
    }
    if (env.mode === "fixture") {
      // Fixture mode does not support live SSE; the workspace's live-stream
      // affordances disable themselves gracefully (FR-013).
      setStatus("idle");
      return undefined;
    }
    if (env.apiUrl === null) {
      setStatus("error");
      callbacksRef.current.onError(new Error("Live mode missing apiUrl"));
      return undefined;
    }

    let cancelled = false;
    let triggers: ReturnType<typeof createCloseTriggers> | null = null;
    let throttledOff: (() => void) | null = null;

    async function loop() {
      while (!cancelled) {
        triggers = createCloseTriggers({
          onThrottled: () => {
            if (cancelled) return;
            setStatus("throttled");
          },
        });

        setStatus("connecting");

        try {
          await openFilteredEvents({
            baseUrl: env.apiUrl as string,
            rid: opts.rid,
            lastEventId: lastEventIdRef.current,
            signal: triggers.signal,
            onOpen: () => {
              if (!cancelled) setStatus("live");
            },
            onEvent: (event) => {
              lastEventIdRef.current = event.id;
              callbacksRef.current.onEvent(event);
            },
            onTerminated: (sentinel) => {
              if (!cancelled) setStatus("terminated");
              callbacksRef.current.onTerminated(sentinel.reason);
              triggers?.unsubscribe();
            },
            onError: (error) => {
              if (!cancelled) setStatus("error");
              callbacksRef.current.onError(error);
            },
          });
        } catch {
          // openFilteredEvents resolves on clean abort; thrown errors fall
          // through to the throttle / re-subscribe logic below.
        }

        if (cancelled) return;

        // If the controller aborted because of the throttle (status ===
        // "throttled"), wait for the tab to become visible again and then
        // resubscribe with the cached lastEventId.
        if (isHidden()) {
          await new Promise<void>((resolve) => {
            const off = onVisibilityChange(() => {
              if (!isHidden()) {
                throttledOff = null;
                off();
                resolve();
              }
            });
            throttledOff = off;
          });
          if (cancelled) return;
          continue;
        }

        // Terminated, errored, or otherwise non-resubscribe-worthy: stop.
        return;
      }
    }

    loop();

    return () => {
      cancelled = true;
      triggers?.unsubscribe();
      throttledOff?.();
    };
  }, [opts.enabled, opts.rid]);

  return {
    status,
    lastEventId: lastEventIdRef.current,
  };
}
