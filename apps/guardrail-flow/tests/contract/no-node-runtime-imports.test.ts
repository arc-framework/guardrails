import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import * as ts from "typescript";

/**
 * Architectural-constraint test for FR-003 (pure Vite SPA, no Node BFF).
 *
 * Walks src/ and asserts that no module imports a Node-runtime-only
 * package. The browser bundle must never depend on next/*, next-server,
 * @vercel/edge, or node: protocol modules.
 */

const SRC_ROOT = join(__dirname, "..", "..", "src");

const FORBIDDEN_PREFIXES = ["next/", "next-server", "@vercel/edge"];
const FORBIDDEN_EXACT = new Set(["next"]);
const FORBIDDEN_REGEXES = [/^node:/];

function listSourceFiles(root: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(root)) {
    const abs = join(root, entry);
    const s = statSync(abs);
    if (s.isDirectory()) {
      out.push(...listSourceFiles(abs));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(abs);
    }
  }
  return out;
}

function collectImportSpecifiers(filePath: string, source: string): string[] {
  const sf = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true);
  const specs: string[] = [];

  function visit(node: ts.Node): void {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      specs.push(node.moduleSpecifier.text);
    }
    if (
      ts.isExportDeclaration(node) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specs.push(node.moduleSpecifier.text);
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments[0] &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      specs.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return specs;
}

function isForbidden(spec: string): boolean {
  if (FORBIDDEN_EXACT.has(spec)) return true;
  if (FORBIDDEN_PREFIXES.some((p) => spec.startsWith(p))) return true;
  if (FORBIDDEN_REGEXES.some((r) => r.test(spec))) return true;
  return false;
}

describe("no-node-runtime-imports", () => {
  it("src/ does not import next/*, next-server, @vercel/edge, or node: modules", () => {
    const files = listSourceFiles(SRC_ROOT);
    expect(files.length).toBeGreaterThan(0);

    const violations: { file: string; specifier: string }[] = [];
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      for (const spec of collectImportSpecifiers(file, source)) {
        if (isForbidden(spec)) {
          violations.push({ file: relative(SRC_ROOT, file), specifier: spec });
        }
      }
    }

    if (violations.length > 0) {
      const detail = violations.map((v) => `  ${v.file} imports ${v.specifier}`).join("\n");
      throw new Error(`FR-003 violation: forbidden Node-runtime imports detected\n${detail}`);
    }
    expect(violations).toEqual([]);
  });
});
