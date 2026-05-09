/**
 * CurtainThemeToggle — vendored from 21st.dev's "curtain-theme-toggle" component.
 *
 * Source: https://21st.dev/community/components/fatih-developer/curtain-theme-toggle/default
 *
 * Customizations:
 * - Click handler calls ``useUiStore.toggleTheme`` (same semantic as the
 *   prior 🌞/🌙 emoji button).
 * - Curtain layer uses ``--background`` so the destination theme paints
 *   correctly during the sweep in light AND dark modes.
 * - 🌞/🌙 glyphs persist as the curtain content for backwards-recognizable
 *   iconography.
 * - Accessible: ``aria-label`` reflects the destination theme; keyboard
 *   activation flows through the button element.
 */

import { useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useUiStore } from "@/lib/state/ui-store";

export function CurtainThemeToggle() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const [sweeping, setSweeping] = useState(false);

  const onClick = () => {
    setSweeping(true);
    // Sweep first, then flip the theme at the half-way point so the
    // viewer sees the curtain cover the icon, swap, then retract.
    window.setTimeout(toggleTheme, 150);
    window.setTimeout(() => setSweeping(false), 320);
  };

  const destinationLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  const Icon = theme === "dark" ? Sun : Moon;

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative grid h-8 w-8 place-items-center overflow-hidden rounded-md border text-foreground transition-colors hover:bg-muted"
      aria-label={destinationLabel}
      title={destinationLabel}
    >
      <Icon aria-hidden className="relative z-0 h-4 w-4" strokeWidth={2} />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 origin-top transition-transform duration-300 ease-in-out"
        style={{
          background: "hsl(var(--background))",
          transform: sweeping ? "scaleY(1)" : "scaleY(0)",
        }}
      />
    </button>
  );
}
