import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import App from "./App";
import { ExplorerRoute } from "./routes/explorer";
import { WorkspaceRoute } from "./routes/workspace";
import { createQueryClient } from "@/lib/state/query-client";
import { useUiStore } from "@/lib/state/ui-store";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import { useLocation } from "react-router-dom";
import "./styles/globals.css";

const queryClient = createQueryClient();

function ThemeRoot({ children }: { children: React.ReactNode }) {
  const theme = useUiStore((s) => s.theme);
  React.useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return <>{children}</>;
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element in index.html");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeRoot>
          <BrowserRouter>
            <Routes>
              <Route element={<App />}>
                <Route index element={<Navigate to="/requests" replace />} />
                <Route
                  path="/requests"
                  element={
                    <RouteBoundary>
                      <ExplorerRoute />
                    </RouteBoundary>
                  }
                />
                <Route
                  path="/requests/:rid"
                  element={
                    <RouteBoundary>
                      <WorkspaceRoute />
                    </RouteBoundary>
                  }
                />
                <Route path="*" element={<NotFoundRoute />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ThemeRoot>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

// Per-route boundary keyed by pathname so navigating between rids
// (or back to the explorer) clears a stuck error state without a full reload.
function RouteBoundary({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  return <ErrorBoundary resetKeys={[pathname]}>{children}</ErrorBoundary>;
}

function NotFoundRoute() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="text-muted-foreground">
        That route does not exist. Try{" "}
        <a href="/requests" className="underline">
          /requests
        </a>
        .
      </p>
    </div>
  );
}
