import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ChatExamplePreset, ChatTurn } from "@/types/chat";
import { useAutoAnimate } from "@formkit/auto-animate/react";
import { Bot, Clock3, FlaskConical, Send, ShieldAlert, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export interface ChatPaneProps {
  turns: ChatTurn[];
  activeTurnId: string | null;
  examples: ChatExamplePreset[];
  examplesLoading: boolean;
  draftModel: string;
  draftPrompt: string;
  draftSystemPrompt: string;
  selectedExampleId: string | null;
  sending: boolean;
  onSelectTurn: (localId: string) => void;
  onDraftModelChange: (value: string) => void;
  onDraftPromptChange: (value: string) => void;
  onDraftSystemPromptChange: (value: string) => void;
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

function TurnBubble({ role, content }: { role: "user" | "assistant"; content: string }) {
  return (
    <div
      className={cn(
        "max-w-[92%] rounded-3xl px-4 py-3 text-sm leading-6 shadow-sm",
        role === "user"
          ? "ml-auto bg-slate-900 text-slate-50 dark:bg-slate-100 dark:text-slate-950"
          : "bg-white/90 text-foreground ring-1 ring-slate-200/80 dark:bg-slate-950/70 dark:ring-slate-800/80",
      )}
    >
      <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] opacity-70">
        {role === "assistant" ? <Bot className="h-3.5 w-3.5" /> : null}
        <span>{role === "user" ? "operator" : "assistant"}</span>
      </div>
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
  );
}

function inspectorLabel(inspector: string): string {
  return inspector === "_baseline" ? "Baseline" : inspector.replaceAll("_", " ");
}

export function ChatPane({
  turns,
  activeTurnId,
  examples,
  examplesLoading,
  draftModel,
  draftPrompt,
  draftSystemPrompt,
  selectedExampleId,
  sending,
  onSelectTurn,
  onDraftModelChange,
  onDraftPromptChange,
  onDraftSystemPromptChange,
  onSelectExample,
  onClearExample,
  onSend,
}: ChatPaneProps) {
  const [showPresets, setShowPresets] = useState(false);
  const [showSystemPrompt, setShowSystemPrompt] = useState(Boolean(draftSystemPrompt));
  const [libraryExampleId, setLibraryExampleId] = useState(selectedExampleId ?? "");
  const [turnListRef] = useAutoAnimate<HTMLDivElement>();

  const selectedExample = selectedExampleId
    ? (examples.find((example) => example.id === selectedExampleId) ?? null)
    : null;

  useEffect(() => {
    setLibraryExampleId(selectedExampleId ?? "");
  }, [selectedExampleId]);

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

  const librarySelectedExample = libraryExampleId
    ? (examples.find((example) => example.id === libraryExampleId) ?? null)
    : null;

  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] border border-slate-200/80 bg-[radial-gradient(circle_at_top_right,rgba(125,211,252,0.22),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.16),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,250,252,0.92))] shadow-[0_24px_80px_-32px_rgba(15,23,42,0.35)] dark:border-slate-800/80 dark:bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.12),transparent_28%),linear-gradient(180deg,rgba(2,6,23,0.96),rgba(15,23,42,0.92))]">
      <div className="border-b border-slate-200/70 px-4 py-4 dark:border-slate-800/80">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-700 dark:text-sky-300">
              Conversation Lab
            </p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight">
              Operator chat with request-bound replay
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Insert a corpus example into the draft, customize it, then send the turn through the
              real chat-completions surface.
            </p>
          </div>
          <Badge
            variant="outline"
            className="border-sky-300/70 bg-white/60 text-sky-950 dark:border-sky-900/80 dark:bg-sky-950/40 dark:text-sky-100"
          >
            {turns.length} turns
          </Badge>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {turns.length === 0 ? (
          <div className="space-y-4">
            <div className="rounded-[26px] border border-dashed border-slate-300/80 bg-white/70 p-5 dark:border-slate-700/80 dark:bg-slate-950/40">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                <Sparkles className="h-4 w-4" />
                Build the next turn deliberately
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Start with a freeform prompt or open the example library below. Presets only fill
                the draft and system context. Nothing is sent until you press{" "}
                <span className="font-medium text-foreground">Send turn</span>.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {examples.slice(0, 3).map((example) => (
                <div
                  key={example.id}
                  className="rounded-[22px] border border-slate-200/80 bg-white/70 p-4 shadow-sm dark:border-slate-800/80 dark:bg-slate-950/50"
                >
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <FlaskConical className="h-3.5 w-3.5" />
                    {DIFFICULTY_LABELS[example.difficulty]}
                  </div>
                  <p className="mt-3 text-sm font-medium leading-6">{example.summary}</p>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                    {example.description}
                  </p>
                </div>
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
                  aria-label={`Focus turn ${turn.rid}`}
                  onClick={() => onSelectTurn(turn.localId)}
                  className={cn(
                    "w-full rounded-[28px] border p-4 text-left transition-all",
                    turn.localId === activeTurnId
                      ? "border-sky-400/80 bg-white/90 shadow-[0_18px_50px_-28px_rgba(14,165,233,0.55)] dark:border-sky-700/80 dark:bg-slate-950/70"
                      : "border-slate-200/80 bg-white/70 hover:border-slate-300 dark:border-slate-800/80 dark:bg-slate-950/45 dark:hover:border-slate-700",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={turn.source === "preset" ? "secondary" : "outline"}>
                        {turn.source === "preset" ? "Preset" : "Manual"}
                      </Badge>
                      {turn.presetSummary ? (
                        <span className="truncate text-xs text-muted-foreground">
                          {turn.presetSummary}
                        </span>
                      ) : null}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatTurnTime(turn.startedAt)}
                    </span>
                  </div>

                  <div className="mt-4 space-y-3">
                    <TurnBubble role="user" content={turn.userMessage} />
                    {turn.status === "sending" ? (
                      <div className="rounded-3xl border border-dashed border-slate-300/80 bg-white/60 px-4 py-4 text-sm text-muted-foreground dark:border-slate-700/80 dark:bg-slate-950/40">
                        Response is in flight. The turn card will hydrate when the request finishes.
                      </div>
                    ) : turn.status === "error" ? (
                      <div className="rounded-3xl border border-red-200/80 bg-red-50/80 px-4 py-4 text-sm text-red-800 dark:border-red-900/80 dark:bg-red-950/30 dark:text-red-200">
                        {turn.errorMessage ?? "Turn failed."}
                      </div>
                    ) : (
                      <TurnBubble
                        role="assistant"
                        content={turn.assistantMessage || "No assistant content returned."}
                      />
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline" className="font-mono">
                      {turn.rid}
                    </Badge>
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
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-900/80">
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

      <div className="border-t border-slate-200/70 bg-white/70 px-4 py-4 backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-950/55">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={showPresets ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowPresets((current) => !current)}
          >
            <FlaskConical className="h-4 w-4" /> Example library
          </Button>
          <Button
            type="button"
            variant={showSystemPrompt || draftSystemPrompt ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setShowSystemPrompt((current) => !current)}
          >
            <Sparkles className="h-4 w-4" /> System note
          </Button>
          {selectedExample ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/80 bg-amber-50 px-3 py-1 text-xs text-amber-950 dark:border-amber-900/80 dark:bg-amber-950/40 dark:text-amber-100">
              <span className="max-w-[18rem] truncate">{selectedExample.summary}</span>
              <button type="button" aria-label="Clear selected example" onClick={onClearExample}>
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ) : null}
        </div>

        {showPresets ? (
          <div className="mt-3 rounded-[24px] border border-slate-200/80 bg-white/80 p-3 dark:border-slate-800/80 dark:bg-slate-950/55">
            {examplesLoading ? (
              <p className="text-sm text-muted-foreground">Loading examples…</p>
            ) : examples.length === 0 ? (
              <p className="text-sm text-muted-foreground">No corpus prompts are available yet.</p>
            ) : (
              <>
                <label
                  htmlFor="chat-example-dropdown"
                  className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground"
                >
                  Existing prompts
                </label>
                <select
                  id="chat-example-dropdown"
                  aria-label="Existing prompts"
                  value={libraryExampleId}
                  onChange={(event) => {
                    const nextId = event.target.value;
                    setLibraryExampleId(nextId);

                    if (!nextId) {
                      return;
                    }

                    const nextExample = examples.find((example) => example.id === nextId) ?? null;
                    if (!nextExample) {
                      return;
                    }

                    onSelectExample(nextExample);
                    setShowSystemPrompt(true);
                    setShowPresets(false);
                  }}
                  className="mt-2 h-11 w-full rounded-2xl border border-slate-200/80 bg-white/90 px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 dark:border-slate-800/80 dark:bg-slate-950/80"
                >
                  <option value="">Choose a corpus prompt</option>
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

                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Select a Swagger-style example and the draft message box will fill immediately.
                </p>

                {librarySelectedExample ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline">
                      {inspectorLabel(librarySelectedExample.inspector)}
                    </Badge>
                    <Badge variant="secondary">
                      {DIFFICULTY_LABELS[librarySelectedExample.difficulty]}
                    </Badge>
                    <Badge
                      variant={actionVariant(
                        librarySelectedExample.expected_action,
                        librarySelectedExample.expected_action === "block",
                      )}
                    >
                      {librarySelectedExample.expected_action}
                    </Badge>
                    <Separator orientation="vertical" className="h-3" />
                    <span>{librarySelectedExample.message_count} source messages</span>
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        {showSystemPrompt || draftSystemPrompt ? (
          <Textarea
            aria-label="System note"
            value={draftSystemPrompt}
            onChange={(event) => onDraftSystemPromptChange(event.target.value)}
            placeholder="Optional system or developer note for this thread"
            className="mt-3 min-h-[88px] rounded-[24px] border-slate-200/80 bg-white/80 dark:border-slate-800/80 dark:bg-slate-950/65"
          />
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
            placeholder="Write the next operator message, or insert a corpus example and edit it here."
            className="min-h-[132px] rounded-[26px] border-slate-200/80 bg-white/85 dark:border-slate-800/80 dark:bg-slate-950/70"
          />

          <div className="rounded-[24px] border border-slate-200/80 bg-white/75 p-3 dark:border-slate-800/80 dark:bg-slate-950/55">
            <label className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Model
            </label>
            <Input
              aria-label="Model"
              value={draftModel}
              onChange={(event) => onDraftModelChange(event.target.value)}
              placeholder="llama3.2"
              className="mt-2 rounded-2xl border-slate-200/80 bg-white/90 dark:border-slate-800/80 dark:bg-slate-950/80"
            />
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Use the preset library to load a Swagger corpus prompt into the draft, then customize
              it before sending.
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
