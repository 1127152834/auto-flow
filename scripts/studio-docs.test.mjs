import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildReport, realModules } from '../apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs'

test('Studio Chinese documentation audit covers exactly the retained catalog', () => {
  const modules = realModules()
  const extensionTypes = [
    'project_data', 'project_manual', 'project_end',
    'proxy_change_ip', 'proxy_change_location', 'proxy_query',
    'trace_mark', 'capture_diagnostics', 'save_trace_segment', 'press_key', 'web_cookie', 'web_storage', 'web_intercept',
  ]
  assert.equal(modules.length, 226)
  assert.equal(new Set(modules.map(module => module.type)).size, 226)
  for (const type of extensionTypes) assert.ok(modules.some(module => module.type === type))
  assert.ok(modules.some(module => module.type === 'text_to_speech'))
  assert.ok(!modules.some(module => module.type === 'read_excel' || module.type === 'notify_feishu' || module.type === 'db_connect' || module.type === 'dp_open_page'))
  const report = buildReport()
  assert.equal(report.failed, false, report.text)
  assert.deepEqual(report.undocumented, [])
})
