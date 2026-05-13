/**
 * Privacy-toggle helper. When the operator's payload visibility is
 * "masked", we render a placeholder dot string with the original
 * length echoed so the operator can still tell whether a field was
 * empty, short, or long without the actual content leaking onto the
 * screen.
 */

export function maskPayload(value: string | null | undefined): string {
  if (value == null || value === "") return "";
  return `••••• ${value.length} chars •••••`;
}

/**
 * Apply ``maskPayload`` to every payload-bearing field on a structurally
 * unknown event-shaped object. Keeps non-payload metadata (sizes,
 * counts, ids, status) visible — only the textual fields get masked.
 */
const PAYLOAD_FIELDS = new Set(["raw_input", "response_text", "text_before", "text_after"]);

export function maskPayloadFields<T extends Record<string, unknown>>(obj: T): T {
  const out = { ...obj } as Record<string, unknown>;
  for (const key of Object.keys(out)) {
    if (PAYLOAD_FIELDS.has(key) && typeof out[key] === "string") {
      out[key] = maskPayload(out[key] as string);
    }
  }
  return out as T;
}
