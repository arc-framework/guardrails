/**
 * Hand-rolled token-level diff. We don't pull in a library for the
 * Phase-1 dashboard — the texts are short, the algorithm is simple,
 * and bundle weight matters more than perfect minimality.
 *
 * Tokenization: split on whitespace and word boundaries. The token
 * boundaries match what an operator visually expects when reading
 * "alice@example.com" → "[EMAIL_ADDRESS]" — the email and the
 * placeholder are each treated as one token, and surrounding whitespace
 * stays atomic so the diff doesn't visually fragment around it.
 *
 * Algorithm: classic O(n*m) longest-common-subsequence backtrack. For
 * a sanitize/redact transformation the typical sizes are well under a
 * few hundred tokens, so the quadratic memory footprint is fine.
 */

export type DiffOpKind = "equal" | "remove" | "add";

export interface DiffOp {
  kind: DiffOpKind;
  text: string;
}

const TOKEN_PATTERN = /\s+|[^\s\w]+|\w+/g;

export function tokenize(input: string): string[] {
  if (!input) return [];
  return input.match(TOKEN_PATTERN) ?? [];
}

export function tokenDiff(before: string, after: string): DiffOp[] {
  const a = tokenize(before);
  const b = tokenize(after);
  const lcs = buildLcsTable(a, b);
  const ops: DiffOp[] = [];

  let i = a.length;
  let j = b.length;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      ops.push({ kind: "equal", text: a[i - 1] as string });
      i -= 1;
      j -= 1;
    } else if ((lcs[i - 1] as number[])[j]! >= (lcs[i] as number[])[j - 1]!) {
      ops.push({ kind: "remove", text: a[i - 1] as string });
      i -= 1;
    } else {
      ops.push({ kind: "add", text: b[j - 1] as string });
      j -= 1;
    }
  }
  while (i > 0) {
    ops.push({ kind: "remove", text: a[i - 1] as string });
    i -= 1;
  }
  while (j > 0) {
    ops.push({ kind: "add", text: b[j - 1] as string });
    j -= 1;
  }

  ops.reverse();
  return mergeAdjacent(ops);
}

function buildLcsTable(a: readonly string[], b: readonly string[]): number[][] {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table: number[][] = Array.from({ length: rows }, () => new Array<number>(cols).fill(0));
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const prevRow = table[i - 1] as number[];
      const curRow = table[i] as number[];
      curRow[j] =
        a[i - 1] === b[j - 1]
          ? (prevRow[j - 1] as number) + 1
          : Math.max(prevRow[j] as number, curRow[j - 1] as number);
    }
  }
  return table;
}

function mergeAdjacent(ops: DiffOp[]): DiffOp[] {
  const out: DiffOp[] = [];
  for (const op of ops) {
    const last = out[out.length - 1];
    if (last && last.kind === op.kind) {
      last.text += op.text;
    } else {
      out.push({ ...op });
    }
  }
  return out;
}
