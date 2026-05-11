import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SendChatCompletionInput } from "@/lib/api/types";

function randomEntropy(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replaceAll("-", "");
  }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

export function createChatRequestId(): string {
  return `chat_${Date.now().toString(36)}_${randomEntropy().slice(0, 20)}`.slice(0, 64);
}

export function useChatTurnMutation() {
  return useMutation({
    mutationFn: (input: SendChatCompletionInput) => api.sendChatCompletion(input),
  });
}
