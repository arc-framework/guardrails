const INLINE_CODE = /`([^`]+)`/;
const BOLD = /\*\*([^*]+)\*\*/;
const ITALIC = /\*([^*]+)\*/;

export function renderCanvasText(text: string): string {
  return text
    .split('\n')
    .map((line) => renderLine(line))
    .join('');
}

function renderLine(line: string): string {
  if (line.startsWith('### ')) {
    return wrapLine('h3', renderInline(line.slice(4)));
  }

  if (line.startsWith('## ')) {
    return wrapLine('h2', renderInline(line.slice(3)));
  }

  if (line.startsWith('# ')) {
    return wrapLine('h1', renderInline(line.slice(2)));
  }

  if (line.startsWith('- ')) {
    return `<div class="arc-canvas-line arc-canvas-line--list"><span class="arc-canvas-bullet">•</span><span>${renderInline(
      line.slice(2),
    )}</span></div>`;
  }

  if (line.trim() === '') {
    return '<div class="arc-canvas-line arc-canvas-line--spacer"></div>';
  }

  return wrapLine('body', renderInline(line));
}

function renderInline(text: string): string {
  let remaining = text;
  let html = '';

  while (remaining.length > 0) {
    const earliest = findEarliestMatch(remaining);

    if (!earliest) {
      html += escapeHtml(remaining);
      break;
    }

    if (earliest.index > 0) {
      html += escapeHtml(remaining.slice(0, earliest.index));
    }

    html += earliest.html;
    remaining = remaining.slice(earliest.index + earliest.length);
  }

  return html;
}

function findEarliestMatch(text: string): {
  index: number;
  length: number;
  html: string;
} | null {
  const matchers = [
    {
      pattern: INLINE_CODE,
      render: (inner: string) =>
        `<code class="arc-canvas-inline arc-canvas-inline--code">${escapeHtml(inner)}</code>`,
    },
    {
      pattern: BOLD,
      render: (inner: string) =>
        `<strong class="arc-canvas-inline arc-canvas-inline--bold">${renderInline(inner)}</strong>`,
    },
    {
      pattern: ITALIC,
      render: (inner: string) =>
        `<em class="arc-canvas-inline arc-canvas-inline--italic">${renderInline(inner)}</em>`,
    },
  ];

  let earliest: { index: number; length: number; html: string } | null = null;

  for (const matcher of matchers) {
    const found = text.match(matcher.pattern);

    if (!found || found.index === undefined) {
      continue;
    }

    if (!earliest || found.index < earliest.index) {
      earliest = {
        index: found.index,
        length: found[0].length,
        html: matcher.render(found[1] ?? ''),
      };
    }
  }

  return earliest;
}

function wrapLine(kind: 'h1' | 'h2' | 'h3' | 'body', html: string): string {
  return `<div class="arc-canvas-line arc-canvas-line--${kind}">${html}</div>`;
}

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
