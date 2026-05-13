import { CurtainThemeToggle } from "@/components/visuals/CurtainThemeToggle";
import { DottedSurface } from "@/components/visuals/DottedSurface";
import { BrandLogo } from "@/components/visuals/brand";
import { env } from "@/lib/env";
import { useUiStore } from "@/lib/state/ui-store";
import { cn } from "@/lib/utils";
import { Eye, EyeOff } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";

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
  connecting: "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-100",
  live: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100 animate-pulse",
  throttled: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
  terminated: "bg-muted text-muted-foreground",
  error: "bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-100",
};

export default function App() {
  const { liveSseStatus, liveSseRid, payloadVisibility, togglePayloadVisibility } = useUiStore(
    (s) => ({
      liveSseStatus: s.liveSseStatus,
      liveSseRid: s.liveSseRid,
      payloadVisibility: s.payloadVisibility,
      togglePayloadVisibility: s.togglePayloadVisibility,
    }),
  );

  const showLiveBadge = env.mode === "live" && liveSseStatus !== "idle" && liveSseRid !== null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link
              to="/requests"
              className="flex items-center gap-2 text-base font-semibold tracking-tight"
            >
              <span aria-hidden className="block h-6 w-6">
                <BrandLogo className="h-full w-full" />
              </span>
              <span>GuardRailFlow</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <NavLink
                to="/chat"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-2.5 py-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    isActive && "bg-muted text-foreground",
                  )
                }
              >
                Chat
              </NavLink>
              <NavLink
                to="/requests"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-2.5 py-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    isActive && "bg-muted text-foreground",
                  )
                }
              >
                Requests
              </NavLink>
              <NavLink
                to="/architecture"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-2.5 py-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    isActive && "bg-muted text-foreground",
                  )
                }
              >
                Architecture
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            {env.mode === "fixture" ? (
              <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900 dark:bg-amber-900/40 dark:text-amber-100">
                <span aria-hidden>🧪</span> FIXTURE
              </span>
            ) : (
              <span className="rounded-md bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100">
                <span aria-hidden>●</span> LIVE
              </span>
            )}
            {showLiveBadge ? (
              <span
                className={cn(
                  "rounded-md px-2 py-1 text-xs font-medium",
                  SSE_STYLES[liveSseStatus],
                )}
                aria-label={`live stream ${liveSseStatus} for ${liveSseRid}`}
                title={`SSE: ${liveSseStatus} (rid ${liveSseRid})`}
              >
                SSE · {SSE_LABELS[liveSseStatus]}
              </span>
            ) : null}
            <button
              type="button"
              onClick={togglePayloadVisibility}
              className="grid h-8 w-8 place-items-center rounded-md border text-foreground transition-colors hover:bg-muted"
              aria-label={
                payloadVisibility === "masked"
                  ? "Show payload text in inspector"
                  : "Mask payload text in inspector"
              }
              aria-pressed={payloadVisibility === "visible"}
              title={
                payloadVisibility === "masked"
                  ? "Payload text is masked. Click to reveal."
                  : "Payload text is visible. Click to mask."
              }
            >
              {payloadVisibility === "masked" ? (
                <EyeOff aria-hidden className="h-4 w-4" strokeWidth={2} />
              ) : (
                <Eye aria-hidden className="h-4 w-4" strokeWidth={2} />
              )}
            </button>
            <CurtainThemeToggle />
          </div>
        </div>
      </header>
      <DottedSurface>
        <main className="flex flex-1 flex-col">
          <Outlet />
        </main>
      </DottedSurface>
    </div>
  );
}
