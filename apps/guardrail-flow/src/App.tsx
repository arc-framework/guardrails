import { Outlet, Link } from "react-router-dom";
import { env } from "@/lib/env";
import { useUiStore } from "@/lib/state/ui-store";

const SSE_LABELS: Record<string, string> = {
  idle: "idle",
  connecting: "connecting…",
  live: "live",
  throttled: "throttled",
  terminated: "terminated",
  error: "error",
};

const SSE_STYLES: Record<string, string> = {
  idle: "bg-muted text-muted-foreground",
  connecting: "bg-blue-200 text-blue-900 dark:bg-blue-800 dark:text-blue-100",
  live: "bg-green-200 text-green-900 dark:bg-green-800 dark:text-green-100 animate-pulse",
  throttled: "bg-yellow-200 text-yellow-900 dark:bg-yellow-800 dark:text-yellow-100",
  terminated: "bg-muted text-muted-foreground",
  error: "bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-100",
};

export default function App() {
  const { theme, toggleTheme, liveSseStatus, liveSseRid } = useUiStore((s) => ({
    theme: s.theme,
    toggleTheme: s.toggleTheme,
    liveSseStatus: s.liveSseStatus,
    liveSseRid: s.liveSseRid,
  }));

  const showLiveBadge = env.mode === "live" && liveSseStatus !== "idle" && liveSseRid !== null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-3">
          <Link to="/requests" className="text-base font-semibold">
            GuardRailFlow
          </Link>
          {env.mode === "fixture" ? (
            <span className="rounded bg-yellow-200 px-2 py-0.5 text-xs font-medium text-yellow-900 dark:bg-yellow-800 dark:text-yellow-100">
              FIXTURE MODE
            </span>
          ) : null}
          {showLiveBadge ? (
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${SSE_STYLES[liveSseStatus]}`}
              aria-label={`live stream ${liveSseStatus} for ${liveSseRid}`}
            >
              SSE · {SSE_LABELS[liveSseStatus]}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={toggleTheme}
          className="rounded border px-2 py-1 text-xs hover:bg-accent"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}
