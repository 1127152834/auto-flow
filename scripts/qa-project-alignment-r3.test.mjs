import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { R3_CASES, REFERENCES, parseR3Options } from './qa-project-alignment-r3.mjs'

test('R3 runner exposes automatic and retained manual modes', () => {
  assert.deepEqual(parseR3Options([]), { manual: false })
  assert.deepEqual(parseR3Options(['--manual']), { manual: true })
})

test('R3 evidence matrix names every required real interaction', () => {
  assert.deepEqual(Object.keys(R3_CASES), [
    'uiEntry', 'multiFieldSave', 'drawerCancel', 'outerReset', 'ruleAtomicity',
    'recordCasAtomicity', 'serviceReconnect', 'unknownOriginalKey', 'visualStates',
  ])
  assert.deepEqual(Object.values(REFERENCES).sort(), [
    '05-data/008-fields-378eb2.png',
    '05-data/009-field-editor-c3de19.png',
    '05-data/010-states-d59f55.png',
    '05-data/012-source-excel-cf611c.png',
    '05-data/014-table-settings-070d7f.png',
    '05-data/100-field-impact-eb086d.png',
  ].sort())
})

test('R3 runner uses the real desktop harness and never auto-approves visual review', async () => {
  const source = await readFile(new URL('./qa-project-alignment-r3.mjs', import.meta.url), 'utf8')
  assert.match(source, /launchElectron/)
  assert.match(source, /--user-data-dir=/)
  assert.match(source, /visualReview:\s*'pending'/)
  assert.match(source, /应用到草稿/)
  assert.match(source, /确认保存字段/)
  assert.match(source, /unknown-original-key/)
  for (const evidence of ['r3-service-reconnect-dirty', 'r3-unknown-save-pending', 'r3-unknown-save-recovered']) assert.match(source, new RegExp(evidence))
  assert.doesNotMatch(source, /visualScore|visualReview:\s*'passed'|native file picker passed/i)
})

test('R3 visual fixtures use UI states and label the synthetic file selection', async () => {
  const source = await readFile(new URL('./qa-project-alignment-r3.mjs', import.meta.url), 'utf8')
  for (const text of ['待整理', '已整理', '待核对', '智能整理', 'r3-field-editor', '取消更改', 'ui-with-E4-file-selection']) assert.match(source, new RegExp(text))
  for (const command of ['schemaconflict', 'lost', 'readerror', 'restore', 'zoom100', 'zoom200']) assert.match(source, new RegExp(command))
  assert.match(source, /manualSchemaConflict/)
  assert.match(source, /expectedContentRevision: record\.contentRevision/)
  assert.match(source, /__r3OriginalOpenDialog/)
  assert.match(source, /r3-replacement\.xlsx/)
  assert.match(source, /R3 manual first operation lookup failed/)
  assert.doesNotMatch(source, /schemaconflict[^\n]*显示自动证据位置|已自动执行真实冲突/)
  assert.match(source, /不代表原生 picker 人工通过/)
})
