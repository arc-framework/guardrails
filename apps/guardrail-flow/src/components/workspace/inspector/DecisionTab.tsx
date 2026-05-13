import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { JsonView } from "@/components/shared/JsonView";
import type { RequestDecisionEnvelope } from "@/types/api";

export interface DecisionTabProps {
  decision: RequestDecisionEnvelope | null;
  loading: boolean;
  error: Error | null;
  available: boolean;
}

export function DecisionTab({ decision, loading, error, available }: DecisionTabProps) {
  if (!available) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        Decision was not captured for this request. The pipeline either short-circuited before the
        decision_emit stage or the decision recorder was disabled.
      </p>
    );
  }
  if (loading) {
    return (
      <div className="px-1">
        <LoadingState rows={4} rowHeight="h-8" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="px-1">
        <ErrorState error={error} />
      </div>
    );
  }
  if (!decision) {
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">No decision payload to display.</p>
    );
  }

  return (
    <div className="flex flex-col gap-3 px-1">
      <header className="grid grid-cols-2 gap-1 text-xs">
        <span className="text-muted-foreground">decision_id</span>
        <span className="text-right font-mono">{decision.decision_id}</span>
        <span className="text-muted-foreground">recorded_at</span>
        <span className="text-right">{decision.recorded_at}</span>
        <span className="text-muted-foreground">payload size</span>
        <span className="text-right">
          <Badge variant="outline">{decision.payload_size_bytes} B</Badge>
        </span>
      </header>
      <JsonView value={decision.decision} maxHeight="480px" />
    </div>
  );
}
