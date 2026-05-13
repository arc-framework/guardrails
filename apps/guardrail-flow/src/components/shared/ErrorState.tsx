import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";

export interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}

function describe(error: unknown): { code: string; message: string } {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message };
  }
  if (error instanceof Error) {
    return { code: error.name || "error", message: error.message };
  }
  return { code: "unknown_error", message: String(error) };
}

export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  const { code, message } = describe(error);
  return (
    <div
      className={cn(
        "flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-6 text-center",
        className,
      )}
      role="alert"
    >
      <div className="space-y-1">
        <p className="text-sm font-medium text-destructive">{code.replace(/_/g, " ")}</p>
        <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
