import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useUiStore } from "@/lib/state/ui-store";
import type {
  LifecycleEventBase,
  RequestDecisionEnvelope,
  RequestWorkspaceManifest,
} from "@/types/api";
import type { InspectorTab, WorkflowNodeState } from "@/types/workflow";
import { StageTab } from "./inspector/StageTab";
import { DecisionTab } from "./inspector/DecisionTab";
import { PolicyTab } from "./inspector/PolicyTab";
import { JsonTab } from "./inspector/JsonTab";

export interface InspectorProps {
  manifest: RequestWorkspaceManifest;
  events: LifecycleEventBase[];
  selectedNode: WorkflowNodeState | null;
  decision: RequestDecisionEnvelope | null;
  decisionLoading: boolean;
  decisionError: Error | null;
  activeTab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
}

const TAB_LABELS: Record<InspectorTab, string> = {
  stage: "Stage",
  decision: "Decision",
  policy: "Policy",
  json: "JSON",
};

export function Inspector({
  manifest,
  events,
  selectedNode,
  decision,
  decisionLoading,
  decisionError,
  activeTab,
  onTabChange,
}: InspectorProps) {
  const collapsed = useUiStore((s) => s.inspectorCollapsed);
  const setCollapsed = useUiStore((s) => s.setInspectorCollapsed);

  if (collapsed) {
    return (
      <aside className="flex flex-col items-center justify-start rounded-md border bg-card p-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(false)}
          aria-label="Expand inspector"
        >
          ←
        </Button>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 flex-col gap-2 rounded-md border bg-card p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Inspector</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse inspector"
        >
          →
        </Button>
      </div>
      <Separator />
      <Tabs
        value={activeTab}
        onValueChange={(v) => onTabChange(v as InspectorTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="grid w-full grid-cols-4">
          {(Object.keys(TAB_LABELS) as InspectorTab[]).map((tab) => (
            <TabsTrigger key={tab} value={tab} className="text-xs">
              {TAB_LABELS[tab]}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="stage" className="mt-2 min-h-0 flex-1 overflow-auto">
          <StageTab selectedNode={selectedNode} events={events} />
        </TabsContent>
        <TabsContent value="decision" className="mt-2 min-h-0 flex-1 overflow-auto">
          <DecisionTab
            decision={decision}
            loading={decisionLoading}
            error={decisionError}
            available={manifest.resources.decision}
          />
        </TabsContent>
        <TabsContent value="policy" className="mt-2 min-h-0 flex-1 overflow-auto">
          <PolicyTab decision={decision} available={manifest.resources.decision} />
        </TabsContent>
        <TabsContent value="json" className="mt-2 min-h-0 flex-1 overflow-auto">
          <JsonTab manifest={manifest} events={events} decision={decision} />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
