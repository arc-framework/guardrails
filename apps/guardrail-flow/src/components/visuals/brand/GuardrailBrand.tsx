/**
 * GuardrailBrand — brand variant of the 21st.dev "cpu-architecture" primitive.
 *
 * Source: https://21st.dev/community/components/svg-ui/cpu-architecture/default
 *
 * Customization: abstract guardrail / shield silhouette. Static — no
 * animation. Useful when the chip needs to feel calmer (e.g. operators
 * screen-sharing during an incident review).
 *
 * Sized for the 24×24 chip slot in the App-shell header.
 */

export function GuardrailBrand({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label="arc-guard guardrail brand"
    >
      <rect width="24" height="24" rx="6" fill="hsl(var(--primary))" />
      <path
        d="M12 4 L19 7 L19 12 C19 16 16 19 12 20 C8 19 5 16 5 12 L5 7 Z"
        fill="hsl(var(--primary-foreground))"
        opacity="0.92"
      />
      <path
        d="M9 12 L11 14 L15 10"
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
