import { ErrorBoundary as ReactErrorBoundary, type FallbackProps } from "react-error-boundary";
import type { ReactNode } from "react";
import { ErrorState } from "./ErrorState";

function Fallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div className="p-4">
      <ErrorState
        error={error instanceof Error ? error : new Error(String(error))}
        onRetry={resetErrorBoundary}
      />
    </div>
  );
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  resetKeys?: unknown[];
}

export function ErrorBoundary({ children, resetKeys }: ErrorBoundaryProps) {
  return (
    <ReactErrorBoundary FallbackComponent={Fallback} resetKeys={resetKeys}>
      {children}
    </ReactErrorBoundary>
  );
}
