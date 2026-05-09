import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { JsonView } from "@/components/shared/JsonView";
import { useDebugQuery } from "@/hooks/useDebugQuery";
import type { DebugSeverity } from "@/types/api";

export interface LogsTabProps {
  rid: string;
}

const SEVERITY_VARIANT: Record<DebugSeverity, "default" | "secondary" | "destructive" | "outline"> =
  {
    DEBUG: "outline",
    INFO: "secondary",
    WARNING: "secondary",
    ERROR: "destructive",
    CRITICAL: "destructive",
  };

export function LogsTab({ rid }: LogsTabProps) {
  const query = useDebugQuery(rid);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !query.hasNextPage) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting && !query.isFetchingNextPage) {
          void query.fetchNextPage();
        }
      },
      { rootMargin: "120px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [query]);

  if (query.isLoading) {
    return <LoadingState rows={5} rowHeight="h-6" />;
  }
  if (query.isError) {
    return <ErrorState error={query.error as Error} onRetry={() => query.refetch()} />;
  }

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  if (items.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No debug entries recorded for this request.</p>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      {items.map((entry) => (
        <details key={`${entry.rid}-${entry.seq}`} className="rounded border bg-background text-xs">
          <summary className="flex cursor-pointer items-center gap-2 px-2 py-1">
            <Badge variant={SEVERITY_VARIANT[entry.severity]}>{entry.severity}</Badge>
            <span className="font-mono text-muted-foreground">{entry.channel}</span>
            <span className="flex-1 truncate">{entry.message}</span>
            <span className="text-muted-foreground">{entry.ts}</span>
          </summary>
          <div className="border-t p-1">
            <JsonView value={entry.metadata} maxHeight="160px" />
          </div>
        </details>
      ))}
      <div ref={sentinelRef} className="h-2" />
      {query.isFetchingNextPage ? (
        <div className="py-2">
          <LoadingState rows={1} rowHeight="h-4" />
        </div>
      ) : null}
      {!query.hasNextPage && items.length > 0 ? (
        <p className="py-2 text-center text-xs text-muted-foreground">— end —</p>
      ) : null}
      {query.hasNextPage && !query.isFetchingNextPage ? (
        <Button variant="outline" size="sm" onClick={() => void query.fetchNextPage()}>
          Load more
        </Button>
      ) : null}
    </div>
  );
}
