import { ChatPane } from "@/components/chat/ChatPane";
import { CorsErrorBanner } from "@/components/shared/CorsErrorBanner";
import { ErrorState } from "@/components/shared/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DebugDock } from "@/components/workspace/DebugDock";
import { LifecycleCanvas } from "@/components/workspace/LifecycleCanvas";
import { useChatExamplesQuery } from "@/hooks/useChatExamplesQuery";
import { createChatRequestId, useChatTurnMutation } from "@/hooks/useChatTurnMutation";
import { useDecisionQuery } from "@/hooks/useDecisionQuery";
import { useFilteredSSE } from "@/hooks/useFilteredSSE";
import { useLifecycleQuery } from "@/hooks/useLifecycleQuery";
import { useRequestDetailQuery } from "@/hooks/useRequestDetailQuery";
import { CorsLikelyError } from "@/lib/api";
import { invalidateOnSseEvent } from "@/lib/state/query-client";
import { useUiStore } from "@/lib/state/ui-store";
import { deriveNodeStates } from "@/lib/workflow/derive-node-state";
import type { RequestSummary } from "@/types/api";
import type { ChatDraftMessage, ChatTurn } from "@/types/chat";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

function buildConversationMessages(
  turns: ChatTurn[],
  systemPrompt: string,
  userPrompt: string,
): ChatDraftMessage[] {
  const messages: ChatDraftMessage[] = [];
  const trimmedSystemPrompt = systemPrompt.trim();
  if (trimmedSystemPrompt) {
    messages.push({ role: "system", content: trimmedSystemPrompt });
  }
  turns
    .filter((turn) => turn.status === "completed")
    .forEach((turn) => {
      messages.push({ role: "user", content: turn.userMessage });
      if (turn.assistantMessage) {
        messages.push({ role: "assistant", content: turn.assistantMessage });
      }
    });
  messages.push({ role: "user", content: userPrompt });
  return messages;
}

function extractSystemPrompt(messages: ChatDraftMessage[]): string {
  return messages
    .filter((message) => message.role === "system" || message.role === "developer")
    .map((message) => message.content.trim())
    .filter(Boolean)
    .join("\n\n");
}

function formatRisk(value: number | null): string {
  if (value === null) return "n/a";
  return value.toFixed(2);
}

function outcomeLabel(summary: RequestSummary | undefined, turn: ChatTurn | null): string {
  if (summary?.final_action) return summary.final_action;
  if (!turn) return "idle";
  if (turn.status === "sending") return "sending";
  return turn.postAction ?? turn.preAction ?? (turn.status === "error" ? "error" : "pass");
}

function SignalCard({
  eyebrow,
  value,
  detail,
}: {
  eyebrow: string;
  value: string;
  detail: string;
}) {
  return (
    <section className="rounded-[24px] border border-border/70 bg-card/85 p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
        {eyebrow}
      </p>
      <p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</p>
    </section>
  );
}

export function ChatWorkspaceRoute() {
  const queryClient = useQueryClient();
  const selectedNodeId = useUiStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useUiStore((state) => state.setSelectedNodeId);
  const dockTab = useUiStore((state) => state.dockTab);
  const setDockTab = useUiStore((state) => state.setDockTab);
  const setLiveSse = useUiStore((state) => state.setLiveSse);
  const resetWorkspaceState = useUiStore((state) => state.resetWorkspaceState);

  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [draftModel, setDraftModel] = useState("llama3.2");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [draftSystemPrompt, setDraftSystemPrompt] = useState("");
  const [selectedExampleId, setSelectedExampleId] = useState<string | null>(null);

  useEffect(() => {
    resetWorkspaceState();
    return () => resetWorkspaceState();
  }, [resetWorkspaceState]);

  const activeTurn = useMemo(() => {
    if (activeTurnId) {
      return turns.find((turn) => turn.localId === activeTurnId) ?? null;
    }
    return turns.length > 0 ? (turns[turns.length - 1] ?? null) : null;
  }, [activeTurnId, turns]);

  useEffect(() => {
    setSelectedNodeId(null);
  }, [activeTurn?.rid, setSelectedNodeId]);

  const activeRid = activeTurn?.status === "completed" ? activeTurn.rid : undefined;

  const examplesQuery = useChatExamplesQuery();
  const sendTurn = useChatTurnMutation();
  const detail = useRequestDetailQuery(activeRid);
  const lifecycle = useLifecycleQuery(activeRid);
  const decisionAvailable = detail.data?.resources.decision ?? false;
  const decision = useDecisionQuery(activeRid, decisionAvailable);

  const sse = useFilteredSSE({
    rid: activeRid ?? "",
    enabled: Boolean(activeRid && detail.data?.summary.live),
    onEvent: (event) => {
      if (!activeRid) return;
      invalidateOnSseEvent(queryClient, activeRid, event);
    },
    onTerminated: () => {
      if (!activeRid) return;
      void queryClient.invalidateQueries({ queryKey: ["request", activeRid] });
    },
    onError: () => undefined,
  });

  useEffect(() => {
    setLiveSse(activeRid ?? null, activeRid ? sse.status : "idle");
    return () => setLiveSse(null, "idle");
  }, [activeRid, sse.status, setLiveSse]);

  const events = useMemo(() => lifecycle.data?.events ?? [], [lifecycle.data?.events]);
  const activeStage = detail.data?.summary.stage ?? null;
  const nodeStates = useMemo(() => deriveNodeStates(events, activeStage), [events, activeStage]);
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodeStates[selectedNodeId as keyof typeof nodeStates] ?? null;
  }, [nodeStates, selectedNodeId]);

  const canvasNotice = useMemo(() => {
    if (!activeTurn) {
      return null;
    }

    if (activeTurn.status === "sending") {
      return {
        className:
          "border-sky-300/80 bg-sky-50/60 text-sky-950 dark:border-sky-900/80 dark:bg-sky-950/30 dark:text-sky-100",
        message:
          "Request is in flight. The canvas stays active now, but every stage remains inactive until replay data lands.",
      };
    }

    if (activeTurn.status === "error") {
      return {
        className:
          "border-red-300/80 bg-red-50/60 text-red-900 dark:border-red-900/80 dark:bg-red-950/30 dark:text-red-100",
        message:
          "This request failed before replay data became available. The canvas remains visible so you can keep the same request context selected.",
      };
    }

    if (detail.isLoading || !detail.data || lifecycle.isLoading || !lifecycle.data) {
      return {
        className: "border-border/70 bg-muted/25 text-muted-foreground",
        message:
          "Replay data is still hydrating. The canvas is already mounted and will light up stage-by-stage as backend artifacts arrive.",
      };
    }

    return null;
  }, [activeTurn, detail.data, detail.isLoading, lifecycle.data, lifecycle.isLoading]);

  const onSelectExample = useCallback((example: NonNullable<typeof examplesQuery.data>[number]) => {
    setSelectedExampleId(example.id);
    setDraftModel(example.model);
    setDraftPrompt(example.user_prompt);
    setDraftSystemPrompt(extractSystemPrompt(example.messages));
  }, []);

  const onSend = useCallback(async () => {
    const prompt = draftPrompt.trim();
    if (!prompt) return;

    const requestId = createChatRequestId();
    const localId = `turn_${requestId}`;
    const startedAt = new Date().toISOString();
    const started = performance.now();
    const selectedExample =
      examplesQuery.data?.find((example) => example.id === selectedExampleId) ?? null;
    const model = draftModel.trim() || "llama3.2";

    const optimisticTurn: ChatTurn = {
      localId,
      requestId,
      rid: requestId,
      userMessage: prompt,
      assistantMessage: null,
      source: selectedExample ? "preset" : "manual",
      presetId: selectedExample?.id ?? null,
      presetSummary: selectedExample?.summary ?? null,
      model,
      startedAt,
      status: "sending",
      blocked: false,
      blockedPhase: null,
      preAction: null,
      postAction: null,
      durationMs: null,
      errorMessage: null,
    };

    setTurns((current) => [...current, optimisticTurn]);
    setActiveTurnId(localId);
    setDraftPrompt("");
    setSelectedExampleId(null);

    try {
      const result = await sendTurn.mutateAsync({
        requestId,
        body: {
          model,
          messages: buildConversationMessages(turns, draftSystemPrompt, prompt),
        },
      });

      const durationMs = Math.round(performance.now() - started);
      setTurns((current) =>
        current.map((turn) =>
          turn.localId === localId
            ? {
                ...turn,
                rid: result.rid,
                assistantMessage: result.assistantMessage || "No assistant content returned.",
                status: "completed",
                blocked: result.blocked,
                blockedPhase: result.blockedPhase,
                preAction: result.preAction,
                postAction: result.postAction,
                durationMs,
              }
            : turn,
        ),
      );
      setDraftSystemPrompt("");
      void queryClient.invalidateQueries({ queryKey: ["request", result.rid] });
      void queryClient.invalidateQueries({ queryKey: ["lifecycle", result.rid] });
      void queryClient.invalidateQueries({ queryKey: ["decision", result.rid] });
    } catch (error) {
      const durationMs = Math.round(performance.now() - started);
      setTurns((current) =>
        current.map((turn) =>
          turn.localId === localId
            ? {
                ...turn,
                status: "error",
                durationMs,
                errorMessage: error instanceof Error ? error.message : "Turn failed.",
              }
            : turn,
        ),
      );
      setDraftPrompt((current) => current || prompt);
      setSelectedExampleId(selectedExample?.id ?? null);
    }
  }, [
    draftModel,
    draftPrompt,
    draftSystemPrompt,
    examplesQuery.data,
    queryClient,
    selectedExampleId,
    sendTurn,
    turns,
  ]);

  const summary = detail.data?.summary;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-3 bg-background p-4 text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/requests" className="text-sm text-muted-foreground hover:underline">
            ← Requests
          </Link>
          <Separator orientation="vertical" className="h-6" />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-700 dark:text-sky-300">
              Continuous chat
            </p>
            <h1 className="text-lg font-semibold tracking-tight">Chat-first guardrail workspace</h1>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="secondary">{turns.length} turns</Badge>
          {activeRid ? (
            <Badge variant="outline" className="font-mono">
              {activeRid}
            </Badge>
          ) : null}
          {activeRid ? (
            <Button asChild variant="outline" size="sm">
              <Link to={`/requests/${activeRid}`}>Open raw workspace</Link>
            </Button>
          ) : null}
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 xl:flex-row">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 xl:flex-[8_1_0%]">
          <div className="grid gap-3 md:grid-cols-4">
            <SignalCard
              eyebrow="Active request"
              value={activeTurn?.status ?? "idle"}
              detail={
                activeTurn?.presetSummary
                  ? `Preset seeded from ${activeTurn.presetSummary}`
                  : "The selected request drives the replay and dock surfaces."
              }
            />
            <SignalCard
              eyebrow="Guard outcome"
              value={outcomeLabel(summary, activeTurn)}
              detail={
                activeTurn?.blockedPhase
                  ? `Blocked during ${activeTurn.blockedPhase.replace("_", " ")}.`
                  : "Outcome comes from the request summary when the turn is captured."
              }
            />
            <SignalCard
              eyebrow="Risk"
              value={formatRisk(summary?.max_risk ?? null)}
              detail={
                summary?.refusal_code
                  ? `Refusal code: ${summary.refusal_code}`
                  : "Risk and refusal data light up when the backend records them."
              }
            />
            <SignalCard
              eyebrow="Artifacts"
              value={
                summary
                  ? `${Number(detail.data?.resources.debug ?? false) + Number(detail.data?.resources.decision ?? false) + Number(detail.data?.resources.lifecycle ?? false)}/3`
                  : "0/3"
              }
              detail={
                summary
                  ? `Decision ${
                      detail.data?.resources.decision
                        ? decision.data
                          ? "captured"
                          : decision.isLoading
                            ? "loading"
                            : "pending"
                        : "off"
                    } · Debug ${detail.data?.resources.debug ? "on" : "off"}`
                  : activeTurn
                    ? "The canvas is mounted now. Lifecycle, decision, and debug artifacts light up as backend replay data arrives."
                    : "Lifecycle, decision, and debug artifacts appear after you send a turn."
              }
            />
          </div>

          <section className="flex min-h-0 flex-1 flex-col rounded-[28px] border border-border/70 bg-card/95 p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  Lifecycle replay
                </p>
                <h2 className="mt-1 text-lg font-semibold">Request observability canvas</h2>
              </div>
              {selectedNode ? (
                <Badge variant="outline">{selectedNode.stage}</Badge>
              ) : summary?.status ? (
                <Badge variant={summary.live ? "default" : "outline"}>{summary.status}</Badge>
              ) : activeTurn ? (
                <Badge variant="outline">{activeTurn.status}</Badge>
              ) : null}
            </div>

            {!activeTurn ? (
              <div className="flex flex-1 items-center justify-center rounded-[24px] border border-dashed border-border/70 bg-muted/25 px-6 text-center text-sm leading-6 text-muted-foreground">
                Send a request from the chat pane, then click any request in the conversation to
                hydrate this canvas and replay its guardrail stages here.
              </div>
            ) : detail.isError ? (
              <div className="flex-1 overflow-auto">
                {detail.error instanceof CorsLikelyError ? (
                  <CorsErrorBanner error={detail.error} />
                ) : (
                  <ErrorState error={detail.error} onRetry={() => detail.refetch()} />
                )}
              </div>
            ) : lifecycle.isError ? (
              <div className="flex-1 overflow-auto">
                <ErrorState error={lifecycle.error} onRetry={() => lifecycle.refetch()} />
              </div>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col gap-3">
                {canvasNotice ? (
                  <div
                    className={`rounded-[20px] border px-4 py-3 text-sm leading-6 ${canvasNotice.className}`}
                  >
                    {canvasNotice.message}
                  </div>
                ) : null}
                <div className="min-h-0 flex-1 rounded-[24px] border border-border/70 bg-background/70">
                  <LifecycleCanvas
                    events={events}
                    activeStage={activeStage}
                    selectedNodeId={selectedNodeId}
                    onNodeSelect={setSelectedNodeId}
                  />
                </div>
              </div>
            )}
          </section>
        </div>

        <div className="min-h-0 xl:flex-[7_1_0%]">
          <ChatPane
            turns={turns}
            activeTurnId={activeTurnId}
            examples={examplesQuery.data ?? []}
            examplesLoading={examplesQuery.isLoading}
            draftModel={draftModel}
            draftPrompt={draftPrompt}
            selectedExampleId={selectedExampleId}
            sending={sendTurn.isPending}
            onSelectTurn={setActiveTurnId}
            onDraftModelChange={setDraftModel}
            onDraftPromptChange={setDraftPrompt}
            onSelectExample={onSelectExample}
            onClearExample={() => {
              setSelectedExampleId(null);
              setDraftSystemPrompt("");
            }}
            onSend={onSend}
          />
        </div>
      </div>

      {activeRid ? (
        <DebugDock
          rid={activeRid}
          events={events}
          sseStatus={sse.status}
          activeTab={dockTab}
          onTabChange={setDockTab}
        />
      ) : (
        <section className="rounded-[24px] border border-dashed border-border/70 bg-muted/25 px-4 py-3 text-sm text-muted-foreground">
          Debug dock stays dormant until a completed turn has an RID to inspect. Choose a turn from
          the chat pane to reactivate lifecycle, backend, and log views.
        </section>
      )}
    </div>
  );
}
