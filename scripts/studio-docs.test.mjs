import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildReport, realModules } from '../apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs'

test('Studio Chinese documentation audit covers exactly the retained catalog', () => {
  const modules = realModules()
  assert.equal(modules.length, 218)
  for (const type of ['project_data', 'project_end', 'proxy_change_ip', 'proxy_change_location', 'proxy_query']) assert.ok(modules.some(module => module.type === type))
  assert.ok(modules.some(module => module.type === 'text_to_speech'))
  assert.ok(!modules.some(module => module.type === 'read_excel' || module.type === 'notify_feishu' || module.type === 'db_connect' || module.type === 'dp_open_page'))
  const report = buildReport()
  assert.equal(report.failed, false, report.text)
  assert.deepEqual(report.undocumented, [])
})
