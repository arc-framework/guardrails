import { ChatWorkspaceRoute } from "@/routes/chat-workspace";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  setSelectedNodeId: vi.fn(),
  setDockTab: vi.fn(),
  setLiveSse: vi.fn(),
  resetWorkspaceState: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue({
    requestId: "chat_test_request",
    rid: "chat_test_request",
    responseId: "chatcmpl_test",
    model: "llama3.2",
    assistantMessage: "Synthetic assistant reply",
    finishReason: "stop",
    blocked: false,
    blockedPhase: null,
    preAction: "pass",
    postAction: "pass",
  }),
}));

vi.mock("@tanstack/react-query", async () => {
  const actual =
    await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
  };
});

vi.mock("react-router-dom", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));

vi.mock("@/lib/state/ui-store", () => ({
  useUiStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      selectedNodeId: null,
      setSelectedNodeId: mocks.setSelectedNodeId,
      dockTab: "lifecycle",
      setDockTab: mocks.setDockTab,
      setLiveSse: mocks.setLiveSse,
      resetWorkspaceState: mocks.resetWorkspaceState,
    }),
}));

vi.mock("@/hooks/useChatExamplesQuery", () => ({
  useChatExamplesQuery: () => ({
    data: [
      {
        id: "_baseline__multi_turn__01",
        inspector: "_baseline",
        difficulty: "easy",
        summary: "Multi-turn conversation with a system prompt",
        description: "Corpus-backed multi-turn example",
        model: "llama3.2",
        messages: [
          { role: "system", content: "You are a concise security advisor." },
          { role: "user", content: "What's a good password length?" },
          { role: "assistant", content: "At least 16 characters." },
          { role: "user", content: "And what about phone numbers like 555-0101?" },
        ],
        user_prompt: "And what about phone numbers like 555-0101?",
        message_count: 4,
        tags: [],
        expected_action: "redact",
        expected_phase: "pre_process",
        refusal_code: null,
      },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useChatTurnMutation", () => ({
  createChatRequestId: () => "chat_test_request",
  useChatTurnMutation: () => ({
    isPending: false,
    mutateAsync: mocks.mutateAsync,
  }),
}));

vi.mock("@/hooks/useRequestDetailQuery", () => ({
  useRequestDetailQuery: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useLifecycleQuery", () => ({
  useLifecycleQuery: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useDecisionQuery", () => ({
  useDecisionQuery: () => ({ data: null, isLoading: false, isError: false, error: null }),
}));

vi.mock("@/hooks/useFilteredSSE", () => ({
  useFilteredSSE: () => ({ status: "idle", lastEventId: null }),
}));

vi.mock("@/lib/state/query-client", () => ({
  invalidateOnSseEvent: vi.fn(),
}));

vi.mock("@/components/shared/ErrorState", () => ({
  ErrorState: () => <div>Error</div>,
}));

vi.mock("@/components/shared/LoadingState", () => ({
  LoadingState: () => <div>Loading</div>,
}));

vi.mock("@/components/shared/CorsErrorBanner", () => ({
  CorsErrorBanner: () => <div>CORS</div>,
}));

vi.mock("@/components/workspace/LifecycleCanvas", () => ({
  LifecycleCanvas: () => <div>Canvas</div>,
}));

vi.mock("@/components/workspace/DebugDock", () => ({
  DebugDock: () => <div>DebugDock</div>,
}));

describe("ChatWorkspaceRoute", () => {
  it("fills the draft immediately when a preset is chosen from the dropdown", async () => {
    const user = userEvent.setup();

    render(<ChatWorkspaceRoute />);

    await user.click(screen.getByRole("button", { name: /example library/i }));
    await user.selectOptions(
      screen.getByLabelText("Existing prompts"),
      "_baseline__multi_turn__01",
    );

    expect(mocks.mutateAsync).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Chat draft")).toHaveValue(
      "And what about phone numbers like 555-0101?",
    );
    expect(screen.getByLabelText("System note")).toHaveValue("You are a concise security advisor.");

    await user.click(screen.getByRole("button", { name: /send turn/i }));

    expect(mocks.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          model: "llama3.2",
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "system",
              content: "You are a concise security advisor.",
            }),
            expect.objectContaining({
              role: "user",
              content: "And what about phone numbers like 555-0101?",
            }),
          ]),
        }),
      }),
    );
  });
});
