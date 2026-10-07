#!/usr/bin/env node
// Copy lint: user-visible strings must not contain internal terms.
// Spec: docs/superpowers/specs/2026-09-30-remediation-m5-experience.md R5-06 / AC5-04
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'out', 'development', 'documentation'])
const SCAN_EXT = /\.(?:ts|tsx)$/
const EXCLUDED_FILE = /(?:\.test\.[cm]?[jt]sx?|\.d\.ts|-api\.ts|\/generated\.ts|\/mock-[^/]*)$/

function walk(dir, out = []) {
  let entries
  try { entries = readdirSync(dir) } catch { return out }
  for (const name of entries) {
    if (SKIP_DIRS.has(name)) continue
    const path = join(dir, name)
    if (statSync(path).isDirectory()) walk(path, out)
    else if (SCAN_EXT.test(path)) out.push(path)
  }
  return out
}

function termPattern(term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return /^[\x00-\x7f]+$/.test(term) ? new RegExp(`(?<![A-Za-z0-9_])${escaped}(?![A-Za-z0-9_])`, 'g') : new RegExp(escaped, 'g')
}

// string literals that are code, not copy: module specifiers, property keys, element access, literal types
function isCodeLiteral(node) {
  const p = node.parent
  if (!p) return false
  if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p) || ts.isLiteralTypeNode(p) || ts.isExternalModuleReference(p)) return true
  if (ts.isPropertyAssignment(p) || ts.isPropertySignature(p) || ts.isEnumMember(p) || ts.isPropertyDeclaration(p)) return p.name === node
  if (ts.isElementAccessExpression(p)) return p.argumentExpression === node
  return false
}

export function lintSource(text, fileName, entries) {
  const kind = fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind)
  const hits = []
  const check = (value, node) => {
    if (!ts.isJsxText(node) && /^[\w.$-]*$/.test(value)) return // bare keys and paths are code, not copy
    for (const entry of entries) {
      for (const match of value.matchAll(termPattern(entry.term))) {
        const index = node.getStart(source) + match.index
        hits.push({ line: source.getLineAndCharacterOfPosition(Math.min(index, node.getEnd())).line + 1, term: entry.term, preferred: entry.preferred })
      }
    }
  }
  const visit = node => {
    if (ts.isStringLiteral(node) && !isCodeLiteral(node)) check(node.text, node)
    else if (ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) check(node.text, node)
    else if (ts.isJsxText(node)) check(node.text, node)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return hits
}

export function lint(root, entries, scanDir = 'apps/desktop/src') {
  const results = []
  for (const file of walk(join(root, scanDir))) {
    const rel = relative(root, file).split(sep).join('/')
    if (EXCLUDED_FILE.test(`/${rel}`)) continue
    const active = entries.filter(entry => !entry.allowedIn.some(prefix => rel === prefix || rel.startsWith(prefix.endsWith('/') ? prefix : `${prefix}/`)))
    if (!active.length) continue
    for (const hit of lintSource(readFileSync(file, 'utf8'), file, active)) results.push({ file: rel, ...hit })
  }
  return results
}

function main() {
  const rootArg = process.argv.indexOf('--root')
  const root = rootArg > 0 ? resolve(process.argv[rootArg + 1]) : resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const entries = JSON.parse(readFileSync(join(root, 'apps/desktop/src/shared/copy/glossary.json'), 'utf8'))
  const results = lint(root, entries)
  for (const hit of results) console.log(`${hit.file}:${hit.line}:${hit.term}:${hit.preferred}`)
  const reportOnly = process.argv.includes('--report-only')
  console.log(`copy-lint: ${results.length} 处界面文案含内部术语${reportOnly ? '（仅报告）' : ''}`)
  if (results.length && !reportOnly) process.exitCode = 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
