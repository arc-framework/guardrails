import { JsonView } from "@/components/shared/JsonView";
import type {
  LifecycleEventBase,
  RequestDecisionEnvelope,
  RequestWorkspaceManifest,
} from "@/types/api";

export interface JsonTabProps {
  manifest: RequestWorkspaceManifest;
  events: LifecycleEventBase[];
  decision: RequestDecisionEnvelope | null;
}

export function JsonTab({ manifest, events, decision }: JsonTabProps) {
  const merged = {
    manifest,
    lifecycle: events,
    decision,
  };
  return (
    <div className="px-1">
      <JsonView value={merged} maxHeight="640px" />
    </div>
  );
}
