import { CorsLikelyError } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface CorsErrorBannerProps {
  error: CorsLikelyError;
  className?: string;
}

/**
 * Day-1 misconfiguration UX: when the backend is reachable but its
 * dashboard_origins setting doesn't include the dashboard's origin, the
 * fetch rejects with a TypeError that the API client maps to
 * CorsLikelyError. Surface it loudly so operators know what to fix.
 */
export function CorsErrorBanner({ error, className }: CorsErrorBannerProps) {
  return (
    <div
      className={cn("rounded-md border border-destructive/40 bg-destructive/5 p-4", className)}
      role="alert"
    >
      <p className="text-sm font-medium text-destructive">Cross-origin request blocked</p>
      <p className="mt-1 text-sm text-muted-foreground">
        The backend rejected a fetch from{" "}
        <code className="font-mono">{error.configuredOrigin}</code>. Add this origin to the
        backend's CORS allow-list:
      </p>
      <pre className="mt-2 rounded bg-muted p-2 text-xs">
        ARC_GUARD_SERVICE_DASHBOARD_ORIGINS={error.configuredOrigin}
      </pre>
      <p className="mt-2 text-xs text-muted-foreground">
        Then restart the service via <code>make docker-up</code>. See the{" "}
        <a
          href="https://github.com/anthropics/arc-guardrails/blob/main/docs/walkthrough/012-dashboard-backend-data-plane.md#operator-knobs"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          dashboard backend walkthrough
        </a>{" "}
        for the full CORS contract.
      </p>
    </div>
  );
}
