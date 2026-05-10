import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ChatExamplePreset } from "@/types/chat";

export function useChatExamplesQuery() {
  return useQuery<ChatExamplePreset[]>({
    queryKey: ["chat-examples"],
    queryFn: () => api.listChatExamples(),
  });
}