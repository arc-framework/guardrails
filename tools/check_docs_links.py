"""Verify that internal Markdown links across ``docs/`` and ``specs/`` resolve.

For every ``*.md`` file under the two trees, parses Markdown links of the form
``[text](path)`` or ``[text](path#anchor)``. External URLs (``http://``,
``https://``, ``mailto:``) are SKIPPED — they are rate-limit hostile and
flaky in CI. Anchors are checked when they reference the same file or
another in-repo file: the target file's headings are extracted and the
anchor must slugify to a real heading.

Exits 0 on all-pass, non-zero with a structured error report on broken links.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LINK_PATTERN = re.compile(
    r"(?<!\!)\[(?P<text>[^\]]+)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)",
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "file://")


def _slugify(heading: str) -> str:
    """GitHub-style heading slug: lowercase, spaces → hyphens, drop punctuation.

    Both single-dash and double-dash forms are produced as candidates so the
    checker accepts either. GitHub itself emits single-dash slugs; the
    double-dash form survives in some legacy hand-written anchors.
    """
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def _slug_candidates(heading: str) -> set[str]:
    """Return both the GitHub canonical slug and the relaxed-collapse slug."""
    base = _slugify(heading)
    collapsed = re.sub(r"-+", "-", base)
    return {base, collapsed}


def _headings_in(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return set()
    headings: set[str] = set()
    for m in HEADING_PATTERN.finditer(text):
        headings.update(_slug_candidates(m.group(2)))
    return headings


def _check_link(source: Path, target: str) -> str | None:
    """Return an error message if the link is broken, else ``None``."""
    if target.startswith(EXTERNAL_PREFIXES):
        return None
    # Skip illustrative placeholders: targets that are literally "..." or that
    # contain placeholder syntax like "<slug>", "<NNN>".
    if target == "..." or "<" in target:
        return None
    if target.startswith("#"):
        anchor = target[1:]
        headings = _headings_in(source)
        if anchor not in headings:
            return f"{source.relative_to(REPO_ROOT)}: anchor '#{anchor}' not found"
        return None

    path_part, _, anchor = target.partition("#")
    if not path_part:
        return None
    target_path = (source.parent / path_part).resolve()
    try:
        target_path.relative_to(REPO_ROOT)
    except ValueError:
        return None
    if not target_path.exists():
        return f"{source.relative_to(REPO_ROOT)}: broken link to '{path_part}' (resolved {target_path})"
    if anchor and target_path.suffix == ".md":
        headings = _headings_in(target_path)
        if anchor not in headings:
            return (
                f"{source.relative_to(REPO_ROOT)}: anchor '#{anchor}' not found in {path_part}"
            )
    return None


SKIP_DIRS = ("docs/university",)


def _is_skipped(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(rel.startswith(prefix) for prefix in SKIP_DIRS)


_FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")


def _strip_code(text: str) -> str:
    """Remove fenced + inline code spans so link parsing ignores them."""
    text = _FENCED_CODE_PATTERN.sub("", text)
    text = _INLINE_CODE_PATTERN.sub("", text)
    return text


def check_links(root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    for sub in ("docs", "specs"):
        for md_path in (root / sub).rglob("*.md"):
            if _is_skipped(md_path, root):
                continue
            try:
                raw = md_path.read_text(encoding="utf-8")
            except Exception as exc:
                errors.append(f"{md_path.relative_to(root)}: cannot read ({exc})")
                continue
            text = _strip_code(raw)
            for match in LINK_PATTERN.finditer(text):
                target = match.group("target")
                err = _check_link(md_path, target)
                if err is not None:
                    errors.append(err)
    return errors


def main(argv: list[str] | None = None) -> int:
    errors = check_links()
    if not errors:
        print("docs links: OK")
        return 0
    sys.stderr.write("broken docs links:\n")
    for err in errors:
        sys.stderr.write(f"  - {err}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
