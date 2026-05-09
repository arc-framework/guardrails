/**
 * PipelineBrand — brand variant of the 21st.dev "cpu-architecture" primitive.
 *
 * Source: https://21st.dev/community/components/svg-ui/cpu-architecture/default
 *
 * Customization: a stylized CPU die with traces fanning out to four pin
 * groups. Animated dashes flow along each trace at staggered offsets so
 * the chip feels alive (mirrors the 21st.dev "current-flowing" trace
 * animation). The original literal "CPU" text is removed; the central
 * die is unbranded so the chip reads as an arc-guard mark.
 *
 * Sized for the 24×24 chip slot in the App-shell header. Traces and
 * pins live in the outer 24×24 box; the central die is 8×8.
 */

const TRACES: ReadonlyArray<{ d: string; delay: number }> = [
  // North-bound traces (3 paths into the top edge)
  { d: "M 8 12 L 8 6  L 6  3", delay: 0 },
  { d: "M 12 12 L 12 3", delay: 0.4 },
  { d: "M 16 12 L 16 6 L 18 3", delay: 0.8 },
  // South-bound traces
  { d: "M 8 12 L 8 18 L 6 21", delay: 0.2 },
  { d: "M 12 12 L 12 21", delay: 0.6 },
  { d: "M 16 12 L 16 18 L 18 21", delay: 1.0 },
  // West-bound traces
  { d: "M 12 8  L 6  8 L 3  6", delay: 0.3 },
  { d: "M 12 12 L 3 12", delay: 0.7 },
  { d: "M 12 16 L 6 16 L 3 18", delay: 1.1 },
  // East-bound traces
  { d: "M 12 8  L 18 8  L 21 6", delay: 0.5 },
  { d: "M 12 12 L 21 12", delay: 0.9 },
  { d: "M 12 16 L 18 16 L 21 18", delay: 1.3 },
];

const PINS: ReadonlyArray<{ cx: number; cy: number }> = [
  { cx: 6, cy: 3 },
  { cx: 12, cy: 3 },
  { cx: 18, cy: 3 },
  { cx: 6, cy: 21 },
  { cx: 12, cy: 21 },
  { cx: 18, cy: 21 },
  { cx: 3, cy: 6 },
  { cx: 3, cy: 12 },
  { cx: 3, cy: 18 },
  { cx: 21, cy: 6 },
  { cx: 21, cy: 12 },
  { cx: 21, cy: 18 },
];

export function PipelineBrand({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label="arc-guard pipeline brand mark"
    >
      <rect width="24" height="24" rx="6" fill="hsl(var(--primary))" />

      {/* Traces — animated dashes flow outward along each path. */}
      <g
        fill="none"
        stroke="hsl(var(--primary-foreground))"
        strokeOpacity="0.55"
        strokeWidth="0.55"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {TRACES.map((t, i) => (
          <path key={i} d={t.d} strokeDasharray="2 3">
            <animate
              attributeName="stroke-dashoffset"
              from="0"
              to="-10"
              dur="2.4s"
              begin={`${t.delay}s`}
              repeatCount="indefinite"
            />
          </path>
        ))}
      </g>

      {/* Outer pins — solid filled dots at the trace endpoints. */}
      <g fill="hsl(var(--primary-foreground))">
        {PINS.map((p, i) => (
          <circle key={i} cx={p.cx} cy={p.cy} r="0.9" />
        ))}
      </g>

      {/* CPU die — central rounded square with a thin inner border so
          it reads as a chip body, not a flat panel. */}
      <rect
        x="8"
        y="8"
        width="8"
        height="8"
        rx="1.4"
        fill="hsl(var(--primary-foreground))"
        opacity="0.95"
      />
      <rect
        x="9.5"
        y="9.5"
        width="5"
        height="5"
        rx="0.6"
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth="0.6"
        opacity="0.85"
      />
    </svg>
  );
}
