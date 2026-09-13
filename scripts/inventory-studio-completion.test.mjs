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
  assert.equal(rows.length, 284)
  assert.equal(new Set(rows.map(row => row.type)).size, 284)
  assert.ok(dependency('open_page').resolved.includes(prefix + 'controls/select-native.tsx#SelectNative'))
  assert.ok(dependency('open_page').external.includes('@radix-ui/react-select#Trigger'))
  assert.deepEqual(dependency('open_page').unresolved, [])
})
test('follows barrel exports to retained database forms instead of guessing by global symbol name', () => {
  assert.ok(dependency('oracle_connect').resolved.includes(prefix + 'config-panels/DatabaseAdvancedConfigs.tsx#OracleConnectConfig'))
  assert.ok(!dependency('oracle_connect').resolved.some(target => target.endsWith('#PostgreSQLConnectConfig')))
})
test('follows lazy imports into actual code tools and their editor dependency', () => {
  assert.ok(dependency('js_script').resolved.includes(prefix + 'JsEditorDialog.tsx#JsEditorDialog'))
  assert.ok(dependency('inject_javascript').resolved.includes(prefix + 'InjectJsEditorDialog.tsx#InjectJsEditorDialog'))
  assert.ok(dependency('js_script').external.some(target => target.startsWith('@monaco-editor/react#')))
})
test('does not silently discard dynamically selected icon components or mark node cases executed', () => {
  const unresolved = new Set(rows.flatMap(row => row.toolDependencies.unresolved))
  assert.ok(unresolved.has(prefix + 'controls/custom-dialogs.tsx#Icon'))
  assert.ok(rows.every(row => row.status === '待核对'))
})
