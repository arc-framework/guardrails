import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createCloseTriggers } from "@/lib/sse/close-triggers";

function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("SSE close-on-tab-hidden-throttle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility("visible");
  });

  afterEach(() => {
    vi.useRealTimers();
    setVisibility("visible");
  });

  it("aborts the signal once the tab has been hidden continuously past the threshold", async () => {
    const onThrottled = vi.fn();
    const triggers = createCloseTriggers({ hiddenThresholdMs: 60_000, onThrottled });

    expect(triggers.signal.aborted).toBe(false);

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(30_000);
    expect(triggers.signal.aborted).toBe(false);
    expect(onThrottled).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(31_000);
    expect(triggers.signal.aborted).toBe(true);
    expect(onThrottled).toHaveBeenCalledTimes(1);
  });

  it("does NOT abort if the tab returns to visible before the threshold", async () => {
    const onThrottled = vi.fn();
    const triggers = createCloseTriggers({ hiddenThresholdMs: 60_000, onThrottled });

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(30_000);
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(60_000);

    expect(triggers.signal.aborted).toBe(false);
    expect(onThrottled).not.toHaveBeenCalled();
  });

  it("explicit unsubscribe aborts immediately regardless of visibility", () => {
    const triggers = createCloseTriggers({ hiddenThresholdMs: 60_000 });
    triggers.unsubscribe();
    expect(triggers.signal.aborted).toBe(true);
  });
});
