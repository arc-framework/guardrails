import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { RequestDecisionEnvelope } from "@/types/api";

export interface PolicyTabProps {
  decision: RequestDecisionEnvelope | null;
  available: boolean;
}

interface PolicyRule {
  id: string;
  matched: boolean;
  action: string;
}

export function PolicyTab({ decision, available }: PolicyTabProps) {
  if (!available || !decision) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        Policy view requires a captured DecisionRecord; none was emitted for this request.
      </p>
    );
  }

  const rules = extractRules(decision.decision);
  const resolved = extractResolvedAction(decision.decision);

  return (
    <div className="flex flex-col gap-3 px-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">resolved action</span>
        {resolved ? (
          <Badge variant={resolvedVariant(resolved)}>{resolved}</Badge>
        ) : (
          <Badge variant="outline">—</Badge>
        )}
      </div>
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
              key={rule.id}
              className="flex items-center justify-between rounded border bg-background px-2 py-1 text-xs"
            >
              <span className="font-mono">{rule.id}</span>
              <div className="flex items-center gap-2">
                <Badge variant={rule.matched ? "default" : "outline"}>
                  {rule.matched ? "matched" : "skipped"}
                </Badge>
                <Badge variant="secondary">{rule.action}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function extractRules(payload: Record<string, unknown>): PolicyRule[] {
  const candidates: unknown[] = [];
  const policy = payload.policy;
  if (policy && typeof policy === "object") {
    candidates.push((policy as Record<string, unknown>).rules);
  }
  candidates.push(payload.rules_evaluated, payload.rules);
  for (const c of candidates) {
    if (Array.isArray(c)) {
      return c
        .filter((r): r is Record<string, unknown> => !!r && typeof r === "object")
        .map((r) => ({
          id: typeof r.id === "string" ? r.id : "(unnamed)",
          matched: r.matched === true,
          action: typeof r.action === "string" ? r.action : "—",
        }));
    }
  }
  return [];
}

function extractResolvedAction(payload: Record<string, unknown>): string | null {
  const action = payload.final_action ?? payload.resolved_action ?? payload.action;
  return typeof action === "string" ? action : null;
}

function resolvedVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
  if (action === "block" || action === "refuse") return "destructive";
  if (action === "pass") return "default";
  return "secondary";
}
