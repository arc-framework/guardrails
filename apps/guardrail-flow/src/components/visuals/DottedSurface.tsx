/**
 * DottedSurface — vendored from 21st.dev's "dotted-surface" component.
 *
 * Source: https://21st.dev/community/components/efferd/dotted-surface/default
 *
 * Customizations:
 * - The 21st.dev original is a Three.js scene (a tilted plane of points
 *   with sine-wave Z-displacement and a perspective camera). We render
 *   the same look using plain Canvas2D + a hand-rolled perspective
 *   projector — no Three.js dependency, ~150 lines of code, well under
 *   the 25 KB visuals bundle budget.
 * - Two superimposed sine waves ripple the plane in real time. Dots
 *   further from the camera shrink and fade per a 1/depth law so the
 *   field reads as genuinely 3D.
 * - Tilt angle is fixed at ~62° from horizontal — matches the upstream
 *   feel where the far edge of the plane disappears toward the horizon.
 * - Pauses on document.hidden, freezes on prefers-reduced-motion.
 * - Theme-aware: light/dark adopt different alphas so the field stays
 *   decorative, not foreground-competing, in both modes.
 * - Render-hint: React Flow canvases (workspace LifecycleCanvas + the
 *   three architecture canvases) MUST set ``position: relative`` +
 *   ``background: hsl(var(--background))`` on their root containers so
 *   the canvas paints opaquely over the dotted backdrop.
 */

import { useUiStore } from "@/lib/state/ui-store";
import { useEffect, useRef, type ReactNode } from "react";
import {
  mountSurfaceBackground,
  type SurfaceBackgroundConfig,
  type SurfaceBackgroundControls,
  type SurfaceBackgroundTheme,
} from "../../../../../shared/visuals/dottedSurface";

export interface DottedSurfaceProps {
  children: ReactNode;
}

export function DottedSurface({ children }: DottedSurfaceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controlsRef = useRef<SurfaceBackgroundControls | null>(null);
  const configRef = useRef<SurfaceBackgroundConfig>({
    amplitude: 18,
    density: 1,
    opacity: 1,
    style: "dotted",
    theme: "light",
  });
  const theme = useUiStore((s) => s.theme);

  configRef.current = {
    ...configRef.current,
    theme: theme === "dark" ? ("dark" as SurfaceBackgroundTheme) : "light",
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const controls = mountSurfaceBackground(canvas, () => configRef.current);
    controlsRef.current = controls;

    return () => {
      controls.destroy();
      controlsRef.current = null;
    };
  }, []);

  useEffect(() => {
    controlsRef.current?.redraw();
  }, [theme]);

  return (
    <div className="relative isolate flex flex-1 flex-col">
      <canvas
        ref={canvasRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 h-full w-full"
      />
      {children}
    </div>
  );
}
