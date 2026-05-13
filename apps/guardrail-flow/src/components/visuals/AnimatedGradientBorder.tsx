/**
 * AnimatedGradientBorder — vendored from 21st.dev's "animated-gradient-border".
 *
 * Source: https://21st.dev/community/components/easemize/animated-gradient-border/default
 *
 * Customizations:
 * - Gradient palette derives from the existing color tokens:
 *     --primary           — leading "active" highlight
 *     --destructive       — when the active stage's runtime is errored / blocked
 *     --muted-foreground  — historical highlight on completed stages
 * - 2s linear infinite sweep when ``active``; static gradient otherwise.
 * - Pure presentational. Used only on the workspace LifecycleCanvas during
 *   replay (NOT on the architecture canvases).
 */

import type { CSSProperties, ReactNode } from "react";

export interface AnimatedGradientBorderProps {
  active: boolean;
  variant?: "primary" | "destructive" | "muted";
  children: ReactNode;
}

const PALETTES: Record<NonNullable<AnimatedGradientBorderProps["variant"]>, string> = {
  primary:
    "linear-gradient(120deg, hsl(var(--primary)) 0%, transparent 40%, hsl(var(--primary)) 100%)",
  destructive:
    "linear-gradient(120deg, hsl(var(--destructive)) 0%, transparent 40%, hsl(var(--destructive)) 100%)",
  muted:
    "linear-gradient(120deg, hsl(var(--muted-foreground)) 0%, transparent 40%, hsl(var(--muted-foreground)) 100%)",
};

const STYLE_KEYFRAMES = `
@keyframes arc_guard_gradient_sweep {
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}
`;

export function AnimatedGradientBorder({
  active,
  variant = "primary",
  children,
}: AnimatedGradientBorderProps) {
  const style: CSSProperties = {
    backgroundImage: PALETTES[variant],
    backgroundSize: "200% 100%",
    backgroundClip: "border-box",
    padding: 2,
    borderRadius: 8,
    ...(active ? { animation: "arc_guard_gradient_sweep 2s linear infinite" } : {}),
  };

  return (
    <>
      {/* Inject the keyframes once per render tree; harmless on duplicates. */}
      <style>{STYLE_KEYFRAMES}</style>
      <div style={style}>
        <div className="rounded-md bg-background">{children}</div>
      </div>
    </>
  );
}
