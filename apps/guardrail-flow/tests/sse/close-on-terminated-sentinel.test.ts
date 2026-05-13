import { describe, expect, it, vi } from "vitest";
import { openFilteredEvents } from "@/lib/sse/filtered-events";

interface FetchSrcArgs {
  onmessage: (msg: { event: string; data: string }) => void;
  onopen?: (response: Response) => Promise<void>;
  signal: AbortSignal;
}

vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: async (_url: string, init: FetchSrcArgs) => {
    if (init.onopen) {
      await init.onopen(new Response(null, { status: 200 }));
    }
    init.onmessage({
      event: "terminated",
      data: JSON.stringify({ rid: "rid-x", reason: "completed" }),
    });
  },
}));

describe("SSE close-on-terminated-sentinel", () => {
  it("invokes onTerminated when the server emits a terminated event", async () => {
    const onEvent = vi.fn();
    const onTerminated = vi.fn();
    const onError = vi.fn();
    const controller = new AbortController();

    await openFilteredEvents({
      baseUrl: "http://example.invalid",
      rid: "rid-x",
      signal: controller.signal,
      onEvent,
      onTerminated,
      onError,
    });

    expect(onTerminated).toHaveBeenCalledTimes(1);
    expect(onTerminated).toHaveBeenCalledWith({ rid: "rid-x", reason: "completed" });
    expect(onEvent).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("rejects malformed terminated payloads via onError", async () => {
    vi.resetModules();
    vi.doMock("@microsoft/fetch-event-source", () => ({
      fetchEventSource: async (_url: string, init: FetchSrcArgs) => {
        init.onmessage({ event: "terminated", data: "{not-json}" });
      },
    }));
    const { openFilteredEvents: reloaded } = await import("@/lib/sse/filtered-events");

    const onTerminated = vi.fn();
    const onError = vi.fn();
    const controller = new AbortController();

    await reloaded({
      baseUrl: "http://example.invalid",
      rid: "rid-x",
      signal: controller.signal,
      onEvent: vi.fn(),
      onTerminated,
      onError,
    });

    expect(onTerminated).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
  });
});
