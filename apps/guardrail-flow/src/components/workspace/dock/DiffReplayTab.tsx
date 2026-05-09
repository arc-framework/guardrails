import { EmptyState } from "@/components/shared/EmptyState";

export function DiffReplayTab() {
  return (
    <EmptyState
      title="Diff/Replay arrives in Phase 2"
      description="This tab will host the in-flight redaction diff and a side-by-side replay of the original vs. sanitized prompt once the upstream Spec captures the necessary lineage."
    />
  );
}
