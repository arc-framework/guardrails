export type ChatRole = "system" | "user" | "assistant" | "tool" | "developer";

export interface ChatDraftMessage {
  role: ChatRole;
  content: string;
  name?: string | null;
}

export interface ChatCompletionRequestPayload {
  model: string;
  messages: ChatDraftMessage[];
  temperature?: number;
  max_tokens?: number;
  user?: string;
}

export interface ChatExamplePreset {
  id: string;
  inspector: string;
  difficulty: "easy" | "medium" | "super_hard";
  summary: string;
  description: string;
  model: string;
  messages: ChatDraftMessage[];
  user_prompt: string;
  message_count: number;
  tags: string[];
  expected_action: string;
  expected_phase: "pre_process" | "post_process";
  refusal_code: string | null;
}

export interface ChatCompletionResult {
  requestId: string;
  rid: string;
  responseId: string;
  model: string;
  assistantMessage: string;
  finishReason: string | null;
  blocked: boolean;
  blockedPhase: "pre_process" | "post_process" | null;
  preAction: string | null;
  postAction: string | null;
}

export type ChatTurnStatus = "sending" | "completed" | "error";

export interface ChatTurn {
  localId: string;
  requestId: string;
  rid: string;
  userMessage: string;
  assistantMessage: string | null;
  source: "manual" | "preset";
  presetId: string | null;
  presetSummary: string | null;
  model: string;
  startedAt: string;
  status: ChatTurnStatus;
  blocked: boolean;
  blockedPhase: "pre_process" | "post_process" | null;
  preAction: string | null;
  postAction: string | null;
  durationMs: number | null;
  errorMessage: string | null;
}