import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/env", () => ({
  env: {
    mode: "live",
    apiUrl: "http://127.0.0.1:8766",
  },
}));

import { liveApi } from "@/lib/api/client";

describe("liveApi.listChatExamples", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("falls back to bundled examples when the backend route is missing", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not Found" }), {
        status: 404,
        statusText: "Not Found",
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const examples = await liveApi.listChatExamples();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8766/chat/examples",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(examples).toHaveLength(3);
    expect(examples.map((example) => example.id)).toContain("_baseline__multi_turn__01");
    expect(examples.map((example) => example.id)).toContain("prompt_injection__easy__03");
  });
});
