import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { execFileSync } from 'node:child_process'
const root = new URL('../', import.meta.url)
execFileSync(process.execPath, ['scripts/inventory-studio-completion.mjs'], { cwd: root })
const rows = JSON.parse(fs.readFileSync(new URL('docs/migration/studio-frontend-completion/capabilities.json', root)))
const dependency = type => rows.find(row => row.type === type).toolDependencies
const prefix = 'apps/desktop/src/renderer/domains/workflows/components/'
test('retains the approved scope and resolves an imported alias to its actual component file', () => {
  assert.equal(rows.length, 227)
  assert.equal(new Set(rows.map(row => row.type)).size, 227)
  assert.ok(dependency('open_page').resolved.includes(prefix + 'controls/select-native.tsx#SelectNative'))
  assert.ok(dependency('open_page').external.includes('@radix-ui/react-select#Trigger'))
  assert.deepEqual(dependency('open_page').unresolved, [])
})
test('excludes database and DP nodes from the delivery inventory', () => {
  const types = new Set(rows.map(row => row.type))
  assert.ok(!types.has('db_connect'))
  assert.ok(!types.has('oracle_connect'))
  assert.ok(!types.has('postgresql_connect'))
  assert.ok(!types.has('mongodb_connect'))
  assert.ok(!types.has('sqlserver_connect'))
  assert.ok(!types.has('sqlite_connect'))
  assert.ok(!types.has('redis_connect'))
  assert.ok(!types.has('dp_open_page'))
})
test('follows lazy imports into actual code tools and their editor dependency', () => {
  assert.ok(dependency('js_script').resolved.includes(prefix + 'JsEditorDialog.tsx#JsEditorDialog'))
  assert.ok(dependency('inject_javascript').resolved.includes(prefix + 'InjectJsEditorDialog.tsx#InjectJsEditorDialog'))
  assert.ok(dependency('js_script').external.some(target => target.startsWith('@monaco-editor/react#')))
})
test('does not silently discard dynamically selected icon components or reconciled node evidence', () => {
  const unresolved = new Set(rows.flatMap(row => row.toolDependencies.unresolved))
  assert.ok(unresolved.has(prefix + 'controls/custom-dialogs.tsx#Icon'))
  assert.ok(rows.every(row => row.status === '已实现且已验收'))
  assert.ok(rows.every(row => row.verifiedCases.some(item => item.id === `NODE.${row.type}.panel-registration`) && row.verifiedCases.some(item => item.id === `NODE.${row.type}.roundtrip`)))
  assert.ok(rows.every(row => row.remaining.length === 0))
  assert.ok(rows.find(row => row.type === 'open_page').verifiedCases.some(item => item.id.startsWith('NODE.branch.open_page.')))
  assert.ok(rows.every(row => row.verifiedCases.every(item => item.status === '已实现且已验收' && item.evidencePath)))
})
