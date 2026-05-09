import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

let capturedSignal: AbortSignal | null = null;

vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: (
    _url: string,
    init: { signal: AbortSignal; onopen?: (r: Response) => Promise<void> },
  ) => {
    capturedSignal = init.signal;
    if (init.onopen) {
      void init.onopen(new Response(null, { status: 200 }));
    }
    return new Promise<void>((_resolve, reject) => {
      init.signal.addEventListener("abort", () => {
        reject(new DOMException("Aborted", "AbortError"));
      });
    });
  },
}));

vi.mock("@/lib/env", () => ({
  env: { mode: "live", apiUrl: "http://example.invalid" },
}));

import { useFilteredSSE } from "@/hooks/useFilteredSSE";

afterEach(() => {
  capturedSignal = null;
});

describe("SSE close-on-route-unmount", () => {
  it("aborts the controller when the hook unmounts", () => {
    const { unmount } = renderHook(() =>
      useFilteredSSE({
        rid: "rid-x",
        enabled: true,
        onEvent: vi.fn(),
        onTerminated: vi.fn(),
        onError: vi.fn(),
      }),
    );

    expect(capturedSignal).not.toBeNull();
    expect(capturedSignal!.aborted).toBe(false);

    unmount();

    expect(capturedSignal!.aborted).toBe(true);
  });
});
