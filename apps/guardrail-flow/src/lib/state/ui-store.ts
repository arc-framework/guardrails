/**
 * Zustand store for ephemeral UI state. Persistent slices (theme, panel
 * collapse, debug-dock height) survive reloads via localStorage; volatile
 * slices (selected node, active tabs) reset on workspace unmount.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { DebugTab, InspectorTab } from "@/types/workflow";

export type Theme = "light" | "dark";

export type LiveSseStatus = "idle" | "connecting" | "live" | "throttled" | "terminated" | "error";

export type PayloadVisibility = "masked" | "visible";

interface PersistentSlice {
  theme: Theme;
  inspectorCollapsed: boolean;
  dockCollapsed: boolean;
  dockHeightPx: number;
  payloadVisibility: PayloadVisibility;
}

interface VolatileSlice {
  selectedNodeId: string | null;
  inspectorTab: InspectorTab;
  dockTab: DebugTab;
  liveSseStatus: LiveSseStatus;
  liveSseRid: string | null;
}

interface UiStore extends PersistentSlice, VolatileSlice {
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setInspectorCollapsed: (v: boolean) => void;
  setDockCollapsed: (v: boolean) => void;
  setDockHeightPx: (v: number) => void;
  setSelectedNodeId: (v: string | null) => void;
  setInspectorTab: (v: InspectorTab) => void;
  setDockTab: (v: DebugTab) => void;
  setLiveSse: (rid: string | null, status: LiveSseStatus) => void;
  setPayloadVisibility: (v: PayloadVisibility) => void;
  togglePayloadVisibility: () => void;
  resetWorkspaceState: () => void;
}

const PERSISTENT_DEFAULTS: PersistentSlice = {
  theme: "light",
  inspectorCollapsed: false,
  dockCollapsed: false,
  dockHeightPx: 240,
  // Default to MASKED — payload-bearing fields are scrubbed in every render
  // until the operator explicitly opts in. Operators sharing screens during
  // an incident review should leave this on the default.
  payloadVisibility: "masked",
};

const VOLATILE_DEFAULTS: VolatileSlice = {
  selectedNodeId: null,
  inspectorTab: "stage",
  dockTab: "lifecycle",
  liveSseStatus: "idle",
  liveSseRid: null,
};

export const useUiStore = create<UiStore>()(
  persist(
    (set) => ({
      ...PERSISTENT_DEFAULTS,
      ...VOLATILE_DEFAULTS,
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
      setInspectorCollapsed: (v) => set({ inspectorCollapsed: v }),
      setDockCollapsed: (v) => set({ dockCollapsed: v }),
      setDockHeightPx: (v) => set({ dockHeightPx: Math.min(Math.max(v, 120), 600) }),
      setSelectedNodeId: (v) => set({ selectedNodeId: v }),
      setInspectorTab: (v) => set({ inspectorTab: v }),
      setDockTab: (v) => set({ dockTab: v }),
      setLiveSse: (rid, status) => set({ liveSseRid: rid, liveSseStatus: status }),
      setPayloadVisibility: (v) => set({ payloadVisibility: v }),
      togglePayloadVisibility: () =>
        set((s) => ({
          payloadVisibility: s.payloadVisibility === "masked" ? "visible" : "masked",
        })),
      resetWorkspaceState: () => set({ ...VOLATILE_DEFAULTS }),
    }),
    {
      name: "guardrail-flow.ui",
      storage: createJSONStorage(() => localStorage),
      partialize: (s): PersistentSlice => ({
        theme: s.theme,
        inspectorCollapsed: s.inspectorCollapsed,
        dockCollapsed: s.dockCollapsed,
        dockHeightPx: s.dockHeightPx,
        payloadVisibility: s.payloadVisibility,
      }),
    },
  ),
);
