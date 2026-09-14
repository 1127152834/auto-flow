import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { test } from 'node:test'

for (const args of [
  ['--output-dir', '--dev'],
  ['--output-dir'],
  ['--unknown'],
  ['--output-dir', '/tmp/a', '--output-dir', '/tmp/b'],
]) {
  test(`project smoke rejects invalid arguments before launching: ${args.join(' ')}`, () => {
    const result = spawnSync(process.execPath, ['scripts/smoke-project-management.mjs', ...args], {
      cwd: new URL('..', import.meta.url), encoding: 'utf8', timeout: 5000,
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /argument|option|requires|duplicate/i)
    assert.doesNotMatch(result.stderr, /Electron|timeout/i)
  })
}
