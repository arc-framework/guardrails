/**
 * Typed per-event-type renderers for the StageTab.
 *
 * Each renderer surfaces the documented fields for one ``LifecycleEvent``
 * subclass as a small Field/Value table. Payload-bearing fields
 * (``raw_input``, ``response_text``, ``text_before/after``) respect the
 * privacy toggle.
 *
 * Unknown event types fall through to the JSON view so we never lose
 * information when a future event type lands before the dashboard
 * registry catches up.
 */

import { JsonView } from "@/components/shared/JsonView";
import { Badge } from "@/components/ui/badge";
import { useUiStore } from "@/lib/state/ui-store";
import { maskPayload } from "@/lib/privacy/mask";
import type { LifecycleEventBase } from "@/types/api";

type FieldRow = { label: string; value: React.ReactNode };

function FieldTable({ rows }: { rows: FieldRow[] }) {
  if (rows.length === 0) return null;
  return (
    <dl className="grid grid-cols-[minmax(110px,auto)_1fr] gap-x-3 gap-y-1 text-xs">
      {rows.map((r) => (
        <div key={r.label} className="contents">
          <dt className="text-muted-foreground">{r.label}</dt>
          <dd className="break-words">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function CodeText({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 text-[10px]">{children}</code>;
}

function PayloadBlock({ value }: { value: string | null | undefined }) {
  const masked = useUiStore((s) => s.payloadVisibility === "masked");
  if (value == null || value === "") {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <pre className="max-h-[200px] overflow-auto whitespace-pre-wrap break-words rounded border bg-background p-2 text-[11px] leading-snug">
      {masked ? maskPayload(value) : value}
    </pre>
  );
}

function asString(v: unknown): string {
  return v == null ? "—" : String(v);
}

function asNumber(v: unknown): string {
  return typeof v === "number" ? String(v) : "—";
}

// ── Per-event-type renderers ─────────────────────────────────────────

function RequestStarted({ ev }: { ev: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          { label: "route", value: <CodeText>{asString(ev.route)}</CodeText> },
          { label: "model", value: asString(ev.model) },
          { label: "msg_count", value: asNumber(ev.msg_count) },
          {
            label: "input_size_bytes",
            value: asNumber(ev.input_size_bytes),
          },
        ]}
      />
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">raw_input</p>
        <PayloadBlock value={ev.raw_input as string | null} />
      </div>
    </div>
  );
}

function IntentCaptured({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "encoder_id", value: <CodeText>{asString(ev.encoder_id)}</CodeText> },
        { label: "intent_size_bytes", value: asNumber(ev.intent_size_bytes) },
      ]}
    />
  );
}

function InspectorRan({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "name", value: <CodeText>{asString(ev.name)}</CodeText> },
        { label: "duration_ms", value: asNumber(ev.duration_ms) },
        { label: "findings_count", value: asNumber(ev.findings_count) },
      ]}
    />
  );
}

function JailbreakDetected({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "detector_id", value: <CodeText>{asString(ev.detector_id)}</CodeText> },
        { label: "category", value: <Badge variant="destructive">{asString(ev.category)}</Badge> },
        { label: "confidence", value: asNumber(ev.confidence) },
        { label: "evidence_reference", value: asString(ev.evidence_reference) },
      ]}
    />
  );
}

function DeceptionScored({ ev }: { ev: Record<string, unknown> }) {
  const band = String(ev.band ?? "not_measured");
  return (
    <FieldTable
      rows={[
        { label: "score_value", value: asNumber(ev.score_value) },
        { label: "score_sentinel", value: asString(ev.score_sentinel) },
        {
          label: "band",
          value: <Badge variant={band === "high" ? "destructive" : "secondary"}>{band}</Badge>,
        },
        { label: "turn_count", value: asNumber(ev.turn_count) },
      ]}
    />
  );
}

function FindingProduced({ ev }: { ev: Record<string, unknown> }) {
  const span = ev.span as [number, number] | undefined;
  return (
    <FieldTable
      rows={[
        {
          label: "entity_type",
          value: <Badge variant="secondary">{asString(ev.entity_type)}</Badge>,
        },
        {
          label: "span",
          value: span ? <CodeText>{`[${span[0]}, ${span[1]}]`}</CodeText> : "—",
        },
        { label: "score", value: asNumber(ev.score) },
        { label: "risk_level", value: asNumber(ev.risk_level) },
        { label: "inspector", value: <CodeText>{asString(ev.inspector)}</CodeText> },
      ]}
    />
  );
}

function SanitizationApplied({ ev }: { ev: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          {
            label: "entity_type",
            value: <Badge variant="secondary">{asString(ev.entity_type)}</Badge>,
          },
          { label: "placeholder", value: <CodeText>{asString(ev.placeholder)}</CodeText> },
          { label: "finding_id", value: <CodeText>{asString(ev.finding_id)}</CodeText> },
        ]}
      />
      {ev.text_before || ev.text_after ? (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">before</p>
            <PayloadBlock value={ev.text_before as string | null} />
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">after</p>
            <PayloadBlock value={ev.text_after as string | null} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PlaceholderMapBuilt({ ev }: { ev: Record<string, unknown> }) {
  const types = (ev.entity_types as string[] | undefined) ?? [];
  return (
    <FieldTable
      rows={[
        { label: "placeholder_count", value: asNumber(ev.placeholder_count) },
        {
          label: "entity_types",
          value: (
            <div className="flex flex-wrap gap-1">
              {types.length > 0
                ? types.map((t) => (
                    <Badge key={t} variant="secondary">
                      {t}
                    </Badge>
                  ))
                : "—"}
            </div>
          ),
        },
      ]}
    />
  );
}

function StrategyExecuted({ ev }: { ev: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          { label: "strategy", value: <CodeText>{asString(ev.strategy)}</CodeText> },
          { label: "finding_id", value: <CodeText>{asString(ev.finding_id)}</CodeText> },
          { label: "text_after_size", value: asNumber(ev.text_after_size) },
        ]}
      />
      {ev.text_before || ev.text_after ? (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">before</p>
            <PayloadBlock value={ev.text_before as string | null} />
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">after</p>
            <PayloadBlock value={ev.text_after as string | null} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FidelityScored({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "score_value", value: asNumber(ev.score_value) },
        { label: "score_sentinel", value: asString(ev.score_sentinel) },
        { label: "band", value: <Badge variant="secondary">{asString(ev.band)}</Badge> },
      ]}
    />
  );
}

function BackendCalled({ ev }: { ev: Record<string, unknown> }) {
  const snap = ev.model_config_snapshot as Record<string, unknown> | null;
  return (
    <FieldTable
      rows={[
        { label: "backend", value: <Badge>{asString(ev.backend)}</Badge> },
        { label: "url", value: <CodeText>{asString(ev.url)}</CodeText> },
        { label: "payload_msg_count", value: asNumber(ev.payload_msg_count) },
        ...(snap
          ? Object.entries(snap).map(([k, v]) => ({
              label: `model_config.${k}`,
              value: asString(v),
            }))
          : []),
      ]}
    />
  );
}

function BackendResponded({ ev }: { ev: Record<string, unknown> }) {
  const tokens = ev.token_usage as Record<string, number> | null;
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          { label: "duration_ms", value: asNumber(ev.duration_ms) },
          {
            label: "http_status",
            value: <Badge variant="secondary">{asNumber(ev.http_status)}</Badge>,
          },
          { label: "finish_reason", value: asString(ev.response_finish_reason) },
          ...(tokens
            ? Object.entries(tokens).map(([k, v]) => ({
                label: `token_usage.${k}`,
                value: asString(v),
              }))
            : []),
        ]}
      />
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
          response_text
        </p>
        <PayloadBlock value={ev.response_text as string | null} />
      </div>
    </div>
  );
}

function ResponseAssembled({ ev }: { ev: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          { label: "response_id", value: <CodeText>{asString(ev.response_id)}</CodeText> },
          { label: "finish_reason", value: asString(ev.finish_reason) },
          {
            label: "arc_guard_blocked",
            value: ev.arc_guard_blocked ? (
              <Badge variant="destructive">true</Badge>
            ) : (
              <Badge variant="outline">false</Badge>
            ),
          },
        ]}
      />
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
          response_text
        </p>
        <PayloadBlock value={ev.response_text as string | null} />
      </div>
    </div>
  );
}

function PolicyResolved({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "max_risk", value: <Badge>{asString(ev.max_risk)}</Badge> },
        {
          label: "resolved_action",
          value: <Badge variant="secondary">{asString(ev.resolved_action)}</Badge>,
        },
        { label: "router", value: <CodeText>{asString(ev.router)}</CodeText> },
      ]}
    />
  );
}

function PolicyRuleEvaluated({ ev }: { ev: Record<string, unknown> }) {
  const matched = ev.outcome === "matched";
  const contributed = ev.contributed_to_action === true;
  return (
    <FieldTable
      rows={[
        { label: "rule_id", value: <CodeText>{asString(ev.rule_id)}</CodeText> },
        {
          label: "outcome",
          value: <Badge variant={matched ? "default" : "outline"}>{asString(ev.outcome)}</Badge>,
        },
        {
          label: "contributed",
          value: contributed ? (
            <Badge>applied</Badge>
          ) : matched ? (
            <Badge variant="secondary">matched</Badge>
          ) : (
            <Badge variant="outline">no</Badge>
          ),
        },
      ]}
    />
  );
}

function DecisionEmitted({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "decision_id", value: <CodeText>{asString(ev.decision_id)}</CodeText> },
        { label: "action", value: <Badge>{asString(ev.action)}</Badge> },
        { label: "max_risk", value: <Badge variant="secondary">{asString(ev.max_risk)}</Badge> },
        { label: "bypass_reason", value: asString(ev.bypass_reason) },
      ]}
    />
  );
}

function RehydrationVerified({ ev }: { ev: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      <FieldTable
        rows={[
          { label: "verifier_id", value: <CodeText>{asString(ev.verifier_id)}</CodeText> },
          { label: "outcome", value: <Badge>{asString(ev.outcome)}</Badge> },
          { label: "rejection_reason", value: asString(ev.rejection_reason) },
        ]}
      />
      {ev.text_before || ev.text_after ? (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">before</p>
            <PayloadBlock value={ev.text_before as string | null} />
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">after</p>
            <PayloadBlock value={ev.text_after as string | null} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RefusalProduced({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        {
          label: "refusal_code",
          value: <Badge variant="destructive">{asString(ev.refusal_code)}</Badge>,
        },
        { label: "human_message_chars", value: asNumber(ev.human_message_chars) },
        { label: "decision_id", value: <CodeText>{asString(ev.decision_id)}</CodeText> },
      ]}
    />
  );
}

function RequestCompleted({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        {
          label: "blocked",
          value: ev.blocked ? (
            <Badge variant="destructive">true</Badge>
          ) : (
            <Badge variant="outline">false</Badge>
          ),
        },
        {
          label: "pre_action",
          value: <Badge variant="secondary">{asString(ev.pre_action)}</Badge>,
        },
        { label: "post_action", value: asString(ev.post_action) },
        { label: "total_duration_ms", value: asNumber(ev.total_duration_ms) },
      ]}
    />
  );
}

function RequestErrored({ ev }: { ev: Record<string, unknown> }) {
  return (
    <FieldTable
      rows={[
        { label: "reason", value: <Badge variant="destructive">{asString(ev.reason)}</Badge> },
        { label: "terminated_by", value: <CodeText>{asString(ev.terminated_by)}</CodeText> },
        { label: "last_event_seq", value: asNumber(ev.last_event_seq) },
      ]}
    />
  );
}

// ── Registry ─────────────────────────────────────────────────────────

const REGISTRY: Record<string, (props: { ev: Record<string, unknown> }) => React.ReactElement> = {
  RequestStarted,
  IntentCaptured,
  InspectorRan,
  JailbreakDetected,
  DeceptionScored,
  FindingProduced,
  SanitizationApplied,
  PlaceholderMapBuilt,
  StrategyExecuted,
  FidelityScored,
  BackendCalled,
  BackendResponded,
  ResponseAssembled,
  PolicyResolved,
  PolicyRuleEvaluated,
  DecisionEmitted,
  RehydrationVerified,
  RefusalProduced,
  RequestCompleted,
  RequestErrored,
};

export function EventRenderer({ event }: { event: LifecycleEventBase }) {
  const Comp = REGISTRY[event.event_type];
  if (!Comp) {
    return <JsonView value={event} maxHeight="200px" />;
  }
  return <Comp ev={event as unknown as Record<string, unknown>} />;
}
