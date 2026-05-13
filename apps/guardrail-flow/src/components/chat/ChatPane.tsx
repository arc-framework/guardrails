import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ChatExamplePreset, ChatTurn } from "@/types/chat";
import { useAutoAnimate } from "@formkit/auto-animate/react";
import { Bot, Clock3, FlaskConical, Send, ShieldAlert, Sparkles, X } from "lucide-react";
import { useMemo } from "react";

export interface ChatPaneProps {
  turns: ChatTurn[];
  activeTurnId: string | null;
  examples: ChatExamplePreset[];
  examplesLoading: boolean;
  draftModel: string;
  draftPrompt: string;
  selectedExampleId: string | null;
  sending: boolean;
  onSelectTurn: (localId: string) => void;
  onDraftModelChange: (value: string) => void;
  onDraftPromptChange: (value: string) => void;
  onSelectExample: (example: ChatExamplePreset) => void;
  onClearExample: () => void;
  onSend: () => void;
}

const DIFFICULTY_LABELS: Record<ChatExamplePreset["difficulty"], string> = {
  easy: "easy",
  medium: "medium",
  super_hard: "super hard",
};

function actionVariant(action: string | null, blocked: boolean) {
  if (blocked || action === "block") return "destructive" as const;
  if (action === "redact" || action === "refuse") return "secondary" as const;
  return "outline" as const;
}

function formatTurnTime(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDuration(value: number | null): string | null {
  if (value === null) return null;
  return `${Math.round(value)} ms`;
}

function TranscriptMessage({ role, content }: { role: "user" | "assistant"; content: string }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[96px_minmax(0,1fr)] sm:items-start">
      <div className="flex items-center gap-2 pt-0.5 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {role === "assistant" ? (
          <Bot className="h-3.5 w-3.5" />
        ) : (
          <span className="h-2.5 w-2.5 rounded-full bg-sky-500 dark:bg-sky-300" />
        )}
        <span>{role === "user" ? "operator" : "assistant"}</span>
      </div>
      <div
        className={cn(
          "border-l pl-4 text-sm leading-6",
          role === "user"
            ? "border-sky-200/80 text-foreground dark:border-sky-900/80"
            : "border-border/70 text-foreground",
        )}
      >
        <p className="whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

function inspectorLabel(inspector: string): string {
  return inspector === "_baseline" ? "Baseline" : inspector.replaceAll("_", " ");
}

function pickFeaturedExamples(examples: ChatExamplePreset[], count: number): ChatExamplePreset[] {
  if (examples.length <= count) {
    return examples;
  }

  const shuffled = [...examples];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    const a = shuffled[index]!;
    const b = shuffled[swapIndex]!;
    shuffled[index] = b;
    shuffled[swapIndex] = a;
  }

  return shuffled.slice(0, count);
}

export function ChatPane({
  turns,
  activeTurnId,
  examples,
  examplesLoading,
  draftModel,
  draftPrompt,
  selectedExampleId,
  sending,
  onSelectTurn,
  onDraftModelChange,
  onDraftPromptChange,
  onSelectExample,
  onClearExample,
  onSend,
}: ChatPaneProps) {
  const [turnListRef] = useAutoAnimate<HTMLDivElement>();

  const selectedExample = selectedExampleId
    ? (examples.find((example) => example.id === selectedExampleId) ?? null)
    : null;

  const groupedExamples = useMemo(() => {
    const groups = new Map<string, ChatExamplePreset[]>();
    examples.forEach((example) => {
      const key = inspectorLabel(example.inspector);
      const existing = groups.get(key);
      if (existing) {
        existing.push(example);
        return;
      }
      groups.set(key, [example]);
    });
    return Array.from(groups.entries());
  }, [examples]);

  const featuredExamples = useMemo(() => pickFeaturedExamples(examples, 3), [examples]);

  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] border border-border/70 bg-card/95 shadow-sm">
      <div className="border-b border-border/70 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-700 dark:text-sky-300">
              Conversation Lab
            </p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight">
              Operator chat with request-bound replay
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Select any request in the thread to render its canvas, or draft the next request and
              send it through the real chat-completions surface.
            </p>
          </div>
          <Badge
            variant="outline"
            className="border-sky-300/70 bg-white/60 text-sky-950 dark:border-sky-900/80 dark:bg-sky-950/40 dark:text-sky-100"
          >
            {turns.length} requests
          </Badge>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {turns.length === 0 ? (
          <div className="space-y-4">
            <div className="rounded-[26px] border border-dashed border-border/70 bg-muted/25 p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Sparkles className="h-4 w-4" />
                Build the next turn deliberately
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Start with a freeform prompt or open the example library below. Presets seed the
                draft, and nothing is sent until you press{" "}
                <span className="font-medium text-foreground">Send turn</span>.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {featuredExamples.map((example) => (
                <button
                  key={example.id}
                  type="button"
                  aria-label={`Use example ${example.summary}`}
                  aria-pressed={selectedExampleId === example.id}
                  onClick={() => onSelectExample(example)}
                  className={cn(
                    "rounded-[22px] border bg-card/75 p-4 text-left shadow-sm transition-colors",
                    selectedExampleId === example.id
                      ? "border-sky-400/80 ring-1 ring-sky-300/70 dark:border-sky-700/80 dark:ring-sky-800/70"
                      : "border-border/70 hover:border-sky-300/70 dark:hover:border-sky-800/70",
                  )}
                >
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <FlaskConical className="h-3.5 w-3.5" />
                    {DIFFICULTY_LABELS[example.difficulty]}
                  </div>
                  <p className="mt-3 text-sm font-medium leading-6">{example.summary}</p>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                    {example.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div ref={turnListRef} className="space-y-4">
            {turns.map((turn) => {
              const outcome = turn.postAction ?? turn.preAction;
              return (
                <button
                  key={turn.localId}
                  type="button"
                  aria-pressed={turn.localId === activeTurnId}
                  aria-label={`Open request ${turn.rid}`}
                  onClick={() => onSelectTurn(turn.localId)}
                  className={cn(
                    "w-full rounded-[24px] border px-4 py-4 text-left transition-all",
                    turn.localId === activeTurnId
                      ? "border-sky-400/80 bg-card shadow-[0_18px_50px_-28px_rgba(14,165,233,0.55)] dark:border-sky-700/80"
                      : "border-border/70 bg-background/40 hover:border-border",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
                        <span>Request</span>
                        <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[11px] tracking-normal text-muted-foreground">
                          {turn.rid}
                        </span>
                        {turn.localId === activeTurnId ? (
                          <span className="text-sky-700 dark:text-sky-300">Canvas active</span>
                        ) : (
                          <span>Click to inspect</span>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Badge variant={turn.source === "preset" ? "secondary" : "outline"}>
                          {turn.source === "preset" ? "Preset" : "Manual"}
                        </Badge>
                        {turn.presetSummary ? (
                          <span className="truncate text-xs text-muted-foreground">
                            {turn.presetSummary}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatTurnTime(turn.startedAt)}
                    </span>
                  </div>

                  <div className="mt-4 space-y-4 border-t border-border/70 pt-4">
                    <TranscriptMessage role="user" content={turn.userMessage} />
                    {turn.status === "sending" ? (
                      <div className="rounded-[20px] border border-dashed border-border/70 bg-muted/25 px-4 py-4 text-sm text-muted-foreground">
                        Response is in flight. The selected request will hydrate its canvas as soon
                        as replay data lands.
                      </div>
                    ) : turn.status === "error" ? (
                      <div className="rounded-[20px] border border-red-200/80 bg-red-50/80 px-4 py-4 text-sm text-red-800 dark:border-red-900/80 dark:bg-red-950/30 dark:text-red-200">
                        {turn.errorMessage ?? "Turn failed."}
                      </div>
                    ) : (
                      <TranscriptMessage
                        role="assistant"
                        content={turn.assistantMessage || "No assistant content returned."}
                      />
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {outcome ? (
                      <Badge variant={actionVariant(outcome, turn.blocked)}>{outcome}</Badge>
                    ) : null}
                    {turn.blockedPhase ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-1 text-red-900 dark:bg-red-950/40 dark:text-red-200">
                        <ShieldAlert className="h-3.5 w-3.5" />
                        {turn.blockedPhase.replace("_", " ")}
                      </span>
                    ) : null}
                    {formatDuration(turn.durationMs) ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
                        <Clock3 className="h-3.5 w-3.5" />
                        {formatDuration(turn.durationMs)}
                      </span>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="border-t border-border/70 bg-background/70 px-4 py-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px]">
            <select
              id="chat-example-dropdown"
              aria-label="Example library"
              value={selectedExampleId ?? ""}
              disabled={examplesLoading || examples.length === 0}
              onChange={(event) => {
                const nextId = event.target.value;
                if (!nextId) {
                  onClearExample();
                  return;
                }

                const nextExample = examples.find((example) => example.id === nextId) ?? null;
                if (!nextExample) {
                  return;
                }

                onSelectExample(nextExample);
              }}
              className="h-9 w-full rounded-full border border-border/70 bg-background/90 px-3 pr-8 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <option value="">
                {examplesLoading
                  ? "Loading examples..."
                  : examples.length === 0
                    ? "No examples available"
                    : "Example library"}
              </option>
              {groupedExamples.map(([group, groupExamples]) => (
                <optgroup key={group} label={group}>
                  {groupExamples.map((example) => (
                    <option key={example.id} value={example.id}>
                      {example.summary}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <FlaskConical className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>
          {selectedExample ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/80 bg-amber-50 px-3 py-1 text-xs text-amber-950 dark:border-amber-900/80 dark:bg-amber-950/40 dark:text-amber-100">
              <span className="max-w-[18rem] truncate">{selectedExample.summary}</span>
              <button type="button" aria-label="Clear selected example" onClick={onClearExample}>
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ) : null}
        </div>

        {selectedExample ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <Badge variant="outline">{inspectorLabel(selectedExample.inspector)}</Badge>
            <Badge variant="secondary">{DIFFICULTY_LABELS[selectedExample.difficulty]}</Badge>
            <Badge
              variant={actionVariant(
                selectedExample.expected_action,
                selectedExample.expected_action === "block",
              )}
            >
              {selectedExample.expected_action}
            </Badge>
            <Separator orientation="vertical" className="h-3" />
            <span>{selectedExample.message_count} source messages</span>
          </div>
        ) : null}

        <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
          <Textarea
            aria-label="Chat draft"
            value={draftPrompt}
            onChange={(event) => onDraftPromptChange(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                if (!sending && draftPrompt.trim()) onSend();
              }
            }}
            placeholder="Write the next operator request, or load a corpus example and refine it here."
            className="min-h-[132px] rounded-[26px] border-border/70 bg-background/85"
          />

          <div className="rounded-[24px] border border-border/70 bg-muted/20 p-3">
            <label className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Model
            </label>
            <Input
              aria-label="Model"
              value={draftModel}
              onChange={(event) => onDraftModelChange(event.target.value)}
              placeholder="llama3.2"
              className="mt-2 rounded-2xl border-border/70 bg-background/90"
            />
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Each send creates a selectable request row that can drive the lifecycle canvas.
            </p>
            <Button
              type="button"
              className="mt-4 w-full rounded-2xl"
              onClick={onSend}
              disabled={sending || !draftPrompt.trim()}
            >
              <Send className="h-4 w-4" /> {sending ? "Sending…" : "Send turn"}
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
}
