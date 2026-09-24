import assert from 'node:assert/strict'
import test from 'node:test'
import { parseLiveArgs } from './qa-pm6-google-live.mjs'

test('live Sheets acceptance can target an installed package and separate evidence', () => {
  const required = ['--config', '/operator/test.json', '--spreadsheet', 'authorized-test', '--sheet', '测试', '--gid', '0', '--label', 'PM9']
  const args = parseLiveArgs([...required, '--executable', '/isolated/AutoFlow.app/Contents/MacOS/AutoFlow', '--output-dir', '/evidence/pm9'])
  assert.equal(args.executable, '/isolated/AutoFlow.app/Contents/MacOS/AutoFlow')
  assert.equal(args.outputDir, '/evidence/pm9')
  assert.equal(args.gid, 0)
  assert.equal(parseLiveArgs(required).executable, undefined)
  assert.throws(() => parseLiveArgs([...required, '--executable']), /--executable requires a value/)
  assert.throws(() => parseLiveArgs([...required, '--output-dir', '--manual']), /--output-dir requires a value/)
  assert.throws(() => parseLiveArgs(required.filter(value => value !== '--config' && value !== '/operator/test.json')), /--config is required/)
})
