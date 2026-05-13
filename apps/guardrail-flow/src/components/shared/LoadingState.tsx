import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface LoadingStateProps {
  /** Number of skeleton rows to render. Default 5. */
  rows?: number;
  /** Optional row height class (e.g. "h-8"). Default "h-8". */
  rowHeight?: string;
  className?: string;
}

export function LoadingState({ rows = 5, rowHeight = "h-8", className }: LoadingStateProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)} aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cn("w-full", rowHeight)} />
      ))}
    </div>
  );
}
