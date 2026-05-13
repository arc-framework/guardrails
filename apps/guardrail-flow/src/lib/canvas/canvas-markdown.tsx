/**
 * Tiny markdown renderer scoped to what Obsidian Canvas text nodes contain:
 * headers (#, ##, ###), **bold**, *italic*, `inline code`, and line breaks.
 * No paragraphs, no lists, no links — keep it small and predictable.
 *
 * Pulling react-markdown for this would be ~30 KB of bundle for a feature
 * that needs five regexes. If a future canvas adds richer content, swap to
 * react-markdown then; for now, keep the bundle lean.
 */

import { type ReactNode } from "react";

const INLINE_CODE = /`([^`]+)`/;
const BOLD = /\*\*([^*]+)\*\*/;
const ITALIC = /\*([^*]+)\*/;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  // We greedily peel inline-code first (highest priority — Obsidian uses
  // backticks for filename refs), then bold, then italic. Anything else is
  // emitted as plain text.
  const parts: ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const matchers: { re: RegExp; render: (inner: string, k: string) => ReactNode }[] = [
      {
        re: INLINE_CODE,
        render: (inner, k) => (
          <code key={k} className="rounded bg-muted px-1 font-mono text-[10px]">
            {inner}
          </code>
        ),
      },
      {
        re: BOLD,
        render: (inner, k) => (
          <strong key={k} className="font-semibold">
            {renderInline(inner, `${k}b`)}
          </strong>
        ),
      },
      {
        re: ITALIC,
        render: (inner, k) => (
          <em key={k} className="italic text-muted-foreground">
            {inner}
          </em>
        ),
      },
    ];

    let earliest: { idx: number; len: number; render: ReactNode } | null = null;

    for (const m of matchers) {
      const found = remaining.match(m.re);
      if (!found || found.index === undefined) continue;
      if (!earliest || found.index < earliest.idx) {
        earliest = {
          idx: found.index,
          len: found[0].length,
          render: m.render(found[1] ?? "", `${keyPrefix}-${key++}`),
        };
      }
    }

    if (!earliest) {
      parts.push(remaining);
      break;
    }
    if (earliest.idx > 0) {
      parts.push(remaining.slice(0, earliest.idx));
    }
    parts.push(earliest.render);
    remaining = remaining.slice(earliest.idx + earliest.len);
  }

  return parts;
}

export function renderCanvasText(text: string): ReactNode {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    let body: ReactNode;
    let className = "";

    if (line.startsWith("### ")) {
      body = renderInline(line.slice(4), `h3-${i}`);
      className = "text-sm font-semibold";
    } else if (line.startsWith("## ")) {
      body = renderInline(line.slice(3), `h2-${i}`);
      className = "text-base font-semibold";
    } else if (line.startsWith("# ")) {
      body = renderInline(line.slice(2), `h1-${i}`);
      className = "text-lg font-bold";
    } else if (line.startsWith("- ")) {
      body = (
        <>
          <span className="mr-1 text-muted-foreground">•</span>
          {renderInline(line.slice(2), `li-${i}`)}
        </>
      );
      className = "text-xs pl-2";
    } else if (line.trim() === "") {
      return <div key={i} className="h-2" />;
    } else {
      body = renderInline(line, `p-${i}`);
      className = "text-xs";
    }

    return (
      <div key={i} className={className}>
        {body}
      </div>
    );
  }) as ReactNode;
}
