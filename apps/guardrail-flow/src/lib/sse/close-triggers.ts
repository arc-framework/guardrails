/**
 * Three close triggers for the filtered SSE subscription (FR-009):
 *
 *   1. Server emits `terminated` sentinel  → handled by the SSE wrapper's
 *                                              onTerminated callback; this
 *                                              module just provides the
 *                                              composed AbortController.
 *   2. Route unmount                       → caller calls returned
 *                                              `unsubscribe()` from the
 *                                              hook's useEffect cleanup.
 *   3. Tab hidden > 60 s                   → background timer aborts the
 *                                              connection; on tab refocus,
 *                                              the hook re-subscribes.
 *
 * This module returns an AbortController whose signal aborts on either
 * route unmount (caller's call to `unsubscribe()`) or the visibility
 * throttle. Trigger #1 is independent of this controller — when the
 * sentinel arrives, the SSE wrapper closes its own loop.
 */

import { waitForTabHiddenFor } from "./visibility";

export interface CloseTriggerOptions {
  /** Duration the tab must remain hidden before throttle fires. */
  hiddenThresholdMs?: number;
  /** Called when the visibility throttle aborts the connection. */
  onThrottled?: () => void;
}

export interface CloseTriggers {
  signal: AbortSignal;
  /** Manually abort (route unmount, hook re-subscribe, etc.). */
  unsubscribe: () => void;
}

const DEFAULT_HIDDEN_THRESHOLD_MS = 60_000;

export function createCloseTriggers(opts: CloseTriggerOptions = {}): CloseTriggers {
  const controller = new AbortController();
  const threshold = opts.hiddenThresholdMs ?? DEFAULT_HIDDEN_THRESHOLD_MS;

  // Trigger #3: tab hidden > threshold ms. waitForTabHiddenFor resolves
  // when the threshold is reached; we then abort the controller.
  waitForTabHiddenFor(threshold, controller.signal)
    .then(() => {
      if (!controller.signal.aborted) {
        controller.abort();
        opts.onThrottled?.();
      }
    })
    .catch(() => {
      // Aborted — nothing to do; the controller is already in the
      // aborted state.
    });

  return {
    signal: controller.signal,
    unsubscribe() {
      if (!controller.signal.aborted) {
        controller.abort();
      }
    },
  };
}
