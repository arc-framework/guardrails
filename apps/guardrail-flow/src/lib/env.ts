/**
 * Build-time env-var parsing. Read once at module init via `import.meta.env`.
 * The mode toggle (live vs fixture) is the dashboard's most important
 * environmental decision — getting it wrong should fail loudly at boot
 * rather than producing a confused runtime.
 */

export type DashboardMode = "live" | "fixture";

interface DashboardEnv {
  mode: DashboardMode;
  apiUrl: string | null;
}

function parseMode(raw: string | undefined): DashboardMode {
  if (raw === undefined || raw === "" || raw === "live") {
    return "live";
  }
  if (raw === "fixture") {
    return "fixture";
  }
  throw new Error(`VITE_DASHBOARD_MODE must be "live" or "fixture" (got "${raw}")`);
}

function parseApiUrl(raw: string | undefined, mode: DashboardMode): string | null {
  if (mode === "fixture") {
    // API URL is irrelevant in fixture mode; the value is unused.
    return null;
  }
  if (!raw || raw.trim() === "") {
    throw new Error(
      "VITE_DASHBOARD_API_URL is required in live mode " +
        '(set it to e.g. "http://127.0.0.1:8766", or run with ' +
        "VITE_DASHBOARD_MODE=fixture)",
    );
  }
  return raw.replace(/\/+$/, "");
}

export const mode: DashboardMode = parseMode(import.meta.env.VITE_DASHBOARD_MODE);

export const env: DashboardEnv = {
  mode,
  apiUrl: parseApiUrl(import.meta.env.VITE_DASHBOARD_API_URL, mode),
};
