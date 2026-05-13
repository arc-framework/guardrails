# Brand variants

Three arc-branded variants of the 21st.dev CPU Architecture primitive. The CPU motif and any literal "CPU" labels are removed in every variant — none of them references "CPU" in the rendered output.

## Variants

| File                 | Glyph                                | Notes                                                                                      |
| -------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------ |
| `PipelineBrand.tsx`  | Stylized 12-stage flow               | Default. The 12 lifecycle stages traced as a pipeline.                                     |
| `WordmarkBrand.tsx`  | `arc` wordmark + animated guard ring | The wordmark with a slow-rotating outer ring that hints at protection.                     |
| `GuardrailBrand.tsx` | Abstract guardrail / shield glyph    | Static silhouette. Useful when the chip needs to feel calmer (e.g. screen-share friendly). |

## Source

All three derive from https://21st.dev/community/components/svg-ui/cpu-architecture/default. The original source paths and traces were preserved structurally; the labels and motif were replaced.

## Customization rationale

- **Animation**: traces run at low opacity (~0.3 alpha) so the chip stays a brand mark, not a focus-stealing animation.
- **Sizing**: chip is 24×24 px in the App-shell header. Each SVG is designed at `viewBox="0 0 24 24"` so it scales cleanly.
- **Color**: `--primary-foreground` on a `--primary` background, matching the prior `GR` chip palette.

## Selection mechanism

`index.ts` re-exports one variant as `BrandLogo`. Switch by editing one line:

```ts
export { PipelineBrand as BrandLogo } from "./PipelineBrand";
//   export { WordmarkBrand as BrandLogo } from "./WordmarkBrand";
//   export { GuardrailBrand as BrandLogo } from "./GuardrailBrand";
```

App-shell imports `BrandLogo`; the operator-on-call decides which variant ships.

## Refresh protocol

If 21st.dev releases an upstream improvement, re-paste the source into the matching brand file, then re-apply the rebrand:

1. Strip CPU iconography and labels.
2. Replace with the variant's chosen motif (pipeline / wordmark / guardrail).
3. Verify low-opacity traces stay below ~0.3 alpha.
4. Confirm the `viewBox` is `0 0 24 24`.

Re-paste-then-rebrand is the canonical path; never ship the default rendering.
