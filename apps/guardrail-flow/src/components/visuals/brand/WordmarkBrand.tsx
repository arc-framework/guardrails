/**
 * WordmarkBrand — brand variant of the 21st.dev "cpu-architecture" primitive.
 *
 * Source: https://21st.dev/community/components/svg-ui/cpu-architecture/default
 *
 * Customization: ``arc`` wordmark with a slow-rotating outer guard ring at
 * low opacity. No CPU motif anywhere.
 *
 * Sized for the 24×24 chip slot in the App-shell header.
 */

export function WordmarkBrand({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" aria-label="arc-guard wordmark brand">
      <rect width="24" height="24" rx="6" fill="hsl(var(--primary))" />
      <g style={{ transformOrigin: "12px 12px" }}>
        <circle
          cx="12"
          cy="12"
          r="9"
          fill="none"
          stroke="hsl(var(--primary-foreground) / 0.3)"
          strokeWidth="0.6"
          strokeDasharray="3 2"
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from="0 12 12"
            to="360 12 12"
            dur="14s"
            repeatCount="indefinite"
          />
        </circle>
      </g>
      <text
        x="12"
        y="15"
        textAnchor="middle"
        fontSize="9"
        fontWeight="700"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fill="hsl(var(--primary-foreground))"
      >
        arc
      </text>
    </svg>
  );
}
