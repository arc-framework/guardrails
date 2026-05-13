/**
 * Page Visibility API helpers. Used by the SSE close-trigger logic to
 * implement the "tab hidden > 60s" throttle from FR-009.
 */

export function isHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

/**
 * Subscribe to visibility-change events. Returns an unsubscribe function.
 */
export function onVisibilityChange(cb: () => void): () => void {
  if (typeof document === "undefined") {
    return () => undefined;
  }
  document.addEventListener("visibilitychange", cb);
  return () => document.removeEventListener("visibilitychange", cb);
}

/**
 * Wait for the tab to be hidden continuously for at least `ms` milliseconds.
 * Resolves when the threshold is reached. Rejects (via the abort signal) if
 * the wait is cancelled (e.g. tab became visible again, or unsubscribe).
 *
 * If the tab is already visible when called, the timer doesn't start until
 * the tab becomes hidden.
 */
export function waitForTabHiddenFor(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const armTimer = () => {
      timeoutId = setTimeout(() => {
        cleanup();
        resolve();
      }, ms);
    };
    const disarmTimer = () => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    };
    const onChange = () => {
      if (isHidden()) {
        if (timeoutId === null) armTimer();
      } else {
        disarmTimer();
      }
    };
    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };
    const cleanup = () => {
      disarmTimer();
      document.removeEventListener("visibilitychange", onChange);
      signal.removeEventListener("abort", onAbort);
    };
    if (isHidden()) armTimer();
    document.addEventListener("visibilitychange", onChange);
    signal.addEventListener("abort", onAbort);
  });
}
