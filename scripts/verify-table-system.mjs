import assert from 'node:assert/strict'
import ts from 'typescript'
import { readdir, readFile } from 'node:fs/promises'
import { resolve, join } from 'node:path'
const root = resolve(import.meta.dirname, '../apps/desktop/src/renderer')
const files = (await readdir(root, { recursive: true })).filter(file => file.endsWith('.tsx') && !/test|development\//.test(file))
const directAllowed = new Set(['shared/components/ui/table.tsx', 'domains/workflows/components/documentation/MarkdownRenderer.tsx'])
const surfaces = []
for (const file of files) {
  const source = await readFile(join(root, file), 'utf8')
  if (/<table(?:\s|>)/.test(source)) assert.ok(directAllowed.has(file), `Unregistered native table: ${file}; use shared Table`)
  const tags = new Set()
  function visit(node) { if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) tags.add(node.tagName.getText()); ts.forEachChild(node, visit) }
  visit(ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX))
  if (tags.has('Table')) {
    assert.ok(source.includes('shared/components/ui/table'), `Table needs shared primitives: ${file}`)
    assert.ok(source.includes('<TableScroll'), `Table needs explicit scroll boundary: ${file}`)
    surfaces.push(file)
  }
}
for (const file of ['domains/workflows/components/documentation/MarkdownRenderer.tsx', 'domains/workflows/components/assistant/MessageBubble.tsx']) {
  const source = await readFile(join(root, file), 'utf8')
  assert.ok(source.includes('af-table') && source.includes('overflow-auto'), `Generated table style/scroll missing: ${file}`)
  surfaces.push(file)
}
const virtual = 'domains/workflows/components/DataTable.tsx'
const source = await readFile(join(root, virtual), 'utf8')
assert.ok(source.includes('af-studio-grid-body') && source.includes('tabIndex={0}'), 'Virtual grid needs accessible actual scroll body')
surfaces.push(virtual)
assert.equal(surfaces.length, 14, 'Update the evidence inventory when real table surfaces change')
console.log(JSON.stringify({ status: 'passed', kind: 'static-source-coverage-only', surfaces }, null, 2))
