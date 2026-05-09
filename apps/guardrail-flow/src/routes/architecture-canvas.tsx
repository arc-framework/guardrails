import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { CanvasViewer } from "@/components/canvas/CanvasViewer";
import { getCanvasBySlug } from "@/lib/canvas/canvas-registry";
import { parseCanvas } from "@/lib/canvas/parse-canvas";
import { deriveNewFlowPath } from "@/lib/canvas/derive-stage-path";
import { useLifecycleQuery } from "@/hooks/useLifecycleQuery";

const RID_REGEX = /^[A-Za-z0-9._-]{1,64}$/;

export function ArchitectureCanvasRoute() {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();
  const ridParam = searchParams.get("rid");
  const rid = ridParam && RID_REGEX.test(ridParam) ? ridParam : null;

  const entry = slug ? getCanvasBySlug(slug) : undefined;

  const parsed = useMemo(() => {
    if (!entry) return null;
    return parseCanvas(entry.data);
  }, [entry]);

  // Only fetch a lifecycle replay if (a) we have a valid rid query param
  // AND (b) the canvas can actually be driven by stage events.
  const lifecycle = useLifecycleQuery(rid && entry?.ridDrivable ? rid : undefined);

  const playbackPath = useMemo(() => {
    if (!entry?.ridDrivable) return [] as string[];
    if (!lifecycle.data) return [] as string[];
    return deriveNewFlowPath(lifecycle.data.events);
  }, [entry?.ridDrivable, lifecycle.data]);

  if (!entry || !parsed) {
    return (
      <div className="p-4">
        <ErrorState error={new Error(`Unknown canvas slug: ${slug ?? "(none)"}`)} />
      </div>
    );
  }

  const isLoadingRid = rid !== null && entry.ridDrivable && lifecycle.isLoading;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-3 p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/architecture" className="text-sm text-muted-foreground hover:underline">
            ← Architecture
          </Link>
          <Separator orientation="vertical" className="h-6" />
          <h1 className="text-sm font-semibold">{entry.title}</h1>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {rid ? (
            <Badge variant="default" className="font-mono">
              rid · {rid}
            </Badge>
          ) : null}
          {entry.ridDrivable && !rid ? (
            <Badge variant="outline">replay any rid via ?rid=…</Badge>
          ) : null}
          {rid && entry.ridDrivable ? (
            <Button asChild variant="outline" size="sm">
              <Link to={`/requests/${encodeURIComponent(rid)}`}>Open workspace</Link>
            </Button>
          ) : null}
        </div>
      </header>

      <p className="text-xs text-muted-foreground">{entry.description}</p>

      <div className="flex-1 overflow-hidden rounded-md border bg-card">
        {isLoadingRid ? (
          <div className="p-4">
            <LoadingState rows={5} rowHeight="h-12" />
          </div>
        ) : (
          <CanvasViewer
            nodes={parsed.nodes}
            edges={parsed.edges}
            playbackPath={playbackPath}
            playbackLabel={rid ? `Replay ${rid}` : "Play"}
          />
        )}
      </div>
    </div>
  );
}
