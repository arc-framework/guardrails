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

import { useEffect, useRef, type ReactNode } from "react";
import { useUiStore } from "@/lib/state/ui-store";

export interface DottedSurfaceProps {
  children: ReactNode;
}

export function DottedSurface({ children }: DottedSurfaceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const theme = useUiStore((s) => s.theme);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const dpr = window.devicePixelRatio || 1;

    // ── Scene setup ──────────────────────────────────────────────────
    // World-space plane at z=0, dots on a 60×60 grid spread across
    // ±300 units in X and Z. The camera sits behind the origin looking
    // forward, tilted down so the plane fills the lower part of the
    // viewport. Wave displaces dots in Y (vertical world space).
    const COLS = 60;
    const ROWS = 60;
    const SPREAD = 300; // world units half-width
    const STEP = (SPREAD * 2) / COLS;
    const AMPLITUDE = 18; // peak wave height
    const FREQ_X = 0.022;
    const FREQ_Z = 0.022;
    const SPEED = 0.0009;

    // Camera position + tilt. The tilt rotates the plane around the X
    // axis by ANGLE rad so the far edge recedes upward toward the
    // viewport top, giving the "looking across a wave field" feel.
    const ANGLE = (62 * Math.PI) / 180; // 62° from horizontal
    const COS_A = Math.cos(ANGLE);
    const SIN_A = Math.sin(ANGLE);
    const CAMERA_Z = -180; // camera offset behind origin
    const CAMERA_Y = 60; // camera height
    const FOCAL = 420; // perspective focal length (px-ish)

    // ── Theme-conditioned colors ─────────────────────────────────────
    const fillBase = theme === "dark" ? "190, 195, 215" : "85, 90, 110";
    const baseAlpha = theme === "dark" ? 0.55 : 0.4;
    const horizonTint = theme === "dark" ? "120, 160, 220" : "80, 110, 200";
    const horizonAlpha = theme === "dark" ? 0.18 : 0.1;

    let raf = 0;
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const drawFrame = (t: number) => {
      ctx.clearRect(0, 0, width, height);
      const cx = width / 2;
      const cy = height / 2;

      // Atmospheric horizon glow — radial gradient sitting above the
      // wave field, suggests depth.
      const grd = ctx.createRadialGradient(
        cx,
        cy * 0.65,
        0,
        cx,
        cy * 0.65,
        Math.max(width, height) * 0.55,
      );
      grd.addColorStop(0, `rgba(${horizonTint}, ${horizonAlpha.toFixed(3)})`);
      grd.addColorStop(1, `rgba(${horizonTint}, 0)`);
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, width, height);

      // Sort by depth (back-to-front) so closer dots paint over distant
      // ones. We compute world Y / projected size here too so we don't
      // do the perspective math twice.
      type Projected = {
        sx: number;
        sy: number;
        size: number;
        alpha: number;
        depth: number;
      };
      const dots: Projected[] = [];

      for (let cIdx = 0; cIdx <= COLS; cIdx += 1) {
        for (let rIdx = 0; rIdx <= ROWS; rIdx += 1) {
          const wx = -SPREAD + cIdx * STEP;
          const wz = -SPREAD + rIdx * STEP;
          // Two superimposed sine waves over (x, z) → world Y.
          const wave = Math.sin(wx * FREQ_X + t * SPEED) + Math.sin(wz * FREQ_Z + t * SPEED * 1.4);
          const wy = (wave / 2) * AMPLITUDE;
          // Camera transform: tilt around X (so far edge of plane
          // rises in screen Y), translate by camera position.
          const ty = wy * COS_A - wz * SIN_A;
          const tz = wy * SIN_A + wz * COS_A - CAMERA_Z;
          if (tz <= 1) continue; // behind / on camera
          // Perspective project.
          const screenX = (wx / tz) * FOCAL + cx;
          const screenY = ((ty - CAMERA_Y) / tz) * FOCAL + cy;
          // Per-dot size + alpha follow 1/depth so far dots shrink + fade.
          const size = (FOCAL / tz) * 1.2;
          if (size < 0.4) continue;
          // Depth fog: alpha falls off in the distance.
          const fog = Math.max(0, Math.min(1, 1 - (tz - 100) / 400));
          const alpha = baseAlpha * fog;
          if (alpha < 0.02) continue;
          dots.push({ sx: screenX, sy: screenY, size, alpha, depth: tz });
        }
      }

      // Painter's algorithm — back-to-front (descending depth).
      dots.sort((a, b) => b.depth - a.depth);
      for (const d of dots) {
        ctx.beginPath();
        ctx.arc(d.sx, d.sy, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${fillBase}, ${d.alpha.toFixed(3)})`;
        ctx.fill();
      }
    };

    const tick = (t: number) => {
      drawFrame(t);
      if (!reduceMotion) raf = requestAnimationFrame(tick);
    };

    if (reduceMotion) {
      drawFrame(0);
    } else {
      raf = requestAnimationFrame(tick);
    }

    const onVisChange = () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
      } else if (!reduceMotion) {
        raf = requestAnimationFrame(tick);
      }
    };
    document.addEventListener("visibilitychange", onVisChange);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisChange);
    };
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
