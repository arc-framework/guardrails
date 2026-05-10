import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { LifecycleEventBase, RequestDecisionEnvelope } from "@/types/api";

export interface PolicyTabProps {
  decision: RequestDecisionEnvelope | null;
  available: boolean;
  /** Lifecycle events for the request. PolicyResolved + PolicyRuleEvaluated
   *  give us per-rule ``contributed_to_action`` even when the
   *  DecisionRecord payload doesn't include it. */
  events?: LifecycleEventBase[];
}

interface PolicyRule {
  key: string;
  id: string;
  matched: boolean;
  /** Set when the rule matched AND drove the resolved action — distinguishes
   *  matched-and-applied from matched-but-overridden. */
  contributedToAction: boolean;
  action: string | null;
}

export function PolicyTab({ decision, available, events = [] }: PolicyTabProps) {
  if (!available || !decision) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        Policy view requires a captured DecisionRecord; none was emitted for this request.
      </p>
    );
  }

  const rules = extractRules(decision.decision, events);
  const resolved = extractResolvedAction(decision.decision);
  const maxRisk = extractMaxRisk(decision.decision, events);
  const bypassReason = extractBypassReason(decision.decision, events);

  return (
    <div className="flex flex-col gap-3 px-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">resolved action</span>
        <div className="flex items-center gap-2">
          {maxRisk ? (
            <Badge variant={riskVariant(maxRisk)} className="uppercase">
              risk {maxRisk}
            </Badge>
          ) : null}
          {resolved ? (
            <Badge variant={resolvedVariant(resolved)}>{resolved}</Badge>
          ) : (
            <Badge variant="outline">—</Badge>
          )}
        </div>
      </div>
      {bypassReason ? (
        <div className="flex items-center gap-2 rounded border border-dashed bg-muted/30 px-2 py-1 text-[11px]">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            bypass
          </span>
          <span>{bypassReason}</span>
        </div>
      ) : null}
      <Separator />
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Rules ({rules.length})
      </h3>
      {rules.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No rule list found in the decision payload. The JSON tab shows the full record.
        </p>
      ) : (
        <ul className="space-y-1">
          {rules.map((rule) => (
            <li
              key={rule.key}
              className="flex items-center justify-between rounded border bg-background px-2 py-1 text-xs"
            >
              <span className="font-mono">{rule.id}</span>
              <div className="flex items-center gap-2">
                <Badge variant={ruleStatusVariant(rule)}>{ruleStatusLabel(rule)}</Badge>
                {rule.action ? <Badge variant="secondary">{rule.action}</Badge> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Extract per-rule details. Canonical source of truth is the
 *  ``PolicyRuleEvaluated`` events emitted by the pipeline (one per rule);
 *  fall back to ``decision.policy.rules`` shape when the events aren't
 *  available (older events / replayed-from-snapshot). */
function extractRules(
  payload: Record<string, unknown>,
  events: LifecycleEventBase[],
): PolicyRule[] {
  const ruleEvents = events.filter((e) => e.event_type === "PolicyRuleEvaluated");
  if (ruleEvents.length > 0) {
    return ruleEvents.map((e, index) => {
      const r = e as unknown as {
        id?: string;
        seq?: number;
        rule_id?: string;
        outcome?: string;
        contributed_to_action?: boolean;
      };
      const matched = r.outcome === "matched";
      return {
        key:
          (typeof r.id === "string" && r.id.length > 0 && r.id) ||
          (typeof r.seq === "number"
            ? `${r.rule_id ?? "(unnamed)"}-${r.seq}`
            : `${r.rule_id ?? "(unnamed)"}-${index}`),
        id: r.rule_id ?? "(unnamed)",
        matched,
        contributedToAction: matched && r.contributed_to_action === true,
        action: null,
      };
    });
  }

  const policy = payload.policy;
  const rules =
    policy && typeof policy === "object" ? (policy as Record<string, unknown>).rules : null;
  if (!Array.isArray(rules)) return [];
  return rules
    .filter((r): r is Record<string, unknown> => !!r && typeof r === "object")
    .map((r, index) => {
      const matched = r.matched === true || r.outcome === "matched";
      return {
        key: `${typeof r.id === "string" ? r.id : "(unnamed)"}-${index}`,
        id: typeof r.id === "string" ? r.id : "(unnamed)",
        matched,
        contributedToAction: matched && r.contributed_to_action === true,
        action: typeof r.action === "string" ? r.action : null,
      };
    });
}

function extractResolvedAction(payload: Record<string, unknown>): string | null {
  const action = payload.final_action ?? payload.resolved_action ?? payload.action;
  return typeof action === "string" ? action : null;
}

function extractMaxRisk(
  payload: Record<string, unknown>,
  events: LifecycleEventBase[],
): string | null {
  const fromPayload = payload.max_risk;
  if (typeof fromPayload === "string" && fromPayload.length > 0) return fromPayload;
  const policyResolved = events.find((e) => e.event_type === "PolicyResolved") as
    | { max_risk?: string }
    | undefined;
  if (policyResolved && typeof policyResolved.max_risk === "string") {
    return policyResolved.max_risk;
  }
  return null;
}

function extractBypassReason(
  payload: Record<string, unknown>,
  events: LifecycleEventBase[],
): string | null {
  const fromPayload = payload.bypass_reason;
  if (typeof fromPayload === "string" && fromPayload.length > 0) return fromPayload;
  const decisionEmitted = events.find((e) => e.event_type === "DecisionEmitted") as
    | { bypass_reason?: string | null }
    | undefined;
  if (decisionEmitted && typeof decisionEmitted.bypass_reason === "string") {
    return decisionEmitted.bypass_reason;
  }
  return null;
}

function resolvedVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
  if (action === "block" || action === "refuse") return "destructive";
  if (action === "pass") return "default";
  return "secondary";
}

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  const upper = risk.toUpperCase();
  if (upper === "CRITICAL" || upper === "HIGH") return "destructive";
  if (upper === "MEDIUM") return "secondary";
  return "outline";
}

function ruleStatusVariant(rule: PolicyRule): "default" | "secondary" | "destructive" | "outline" {
  if (rule.contributedToAction) return "default";
  if (rule.matched) return "secondary";
  return "outline";
}

function ruleStatusLabel(rule: PolicyRule): string {
  if (rule.contributedToAction) return "applied";
  if (rule.matched) return "matched";
  return "skipped";
}
