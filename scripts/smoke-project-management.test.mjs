import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { test } from 'node:test'

for (const script of ['smoke-project-management.mjs', 'smoke-project-management-desktop.mjs']) {
for (const args of [
  ['--output-dir', '--dev'],
  ['--output-dir'],
  ['--unknown'],
  ['--executable'],
  ['--executable', '   '],
  ['--output-dir', '/tmp/a', '--output-dir', '/tmp/b'],
]) {
  test(`${script} rejects invalid arguments before launching: ${args.join(' ')}`, () => {
    const result = spawnSync(process.execPath, [`scripts/${script}`, ...args], {
      cwd: new URL('..', import.meta.url), encoding: 'utf8', timeout: 5000,
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /argument|option|requires|duplicate/i)
    assert.doesNotMatch(result.stderr, /Electron|timeout/i)
  })
}
}

for (const script of ['smoke-project-management.mjs', 'smoke-project-management-desktop.mjs']) {
  test(`${script} rejects fake sidecar environment before launch`, () => {
    const result = spawnSync(process.execPath, [`scripts/${script}`], {
      cwd: new URL('..', import.meta.url), encoding: 'utf8', timeout: 5000,
      env: { ...process.env, AUTOFLOW_QA_SIDECAR_MODULE: 'tests.qa.pm8_sidecar' },
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /production smoke forbids injected environment/)
    assert.doesNotMatch(result.stderr, /Electron|timeout/)
  })
}

test('concurrent writes retry declared busy responses with the original command identity', async () => {
  const { checkConcurrentRecordWrites } = await import('./smoke-project-management.mjs')
  const keys = [], accepted = new Set()
  let fatal = false
  async function api(path, options = {}) {
    if (path.endsWith('/tables')) return { tableId: 't', tableRevision: 1, datasetGeneration: 'g' }
    if (path.endsWith('/fields')) return { field: { ref: { fieldId: 'f' } } }
    if (path.endsWith('/records')) {
      keys.push(options.key)
      accepted.add(options.key)
      if (keys.length === 1) throw new Error('busy', { cause: { status: fatal ? 500 : 503, code: 'DATABASE_BUSY' } })
      return {}
    }
    return { recordCount: accepted.size }
  }
  const result = await checkConcurrentRecordWrites(api, '/projects/p', 1)
  assert.equal(result.busyRetries, 1)
  assert.equal(keys.length, 2)
  assert.match(keys[0], /^[0-9a-f-]{36}$/)
  assert.equal(keys[0], keys[1])
  assert.equal(accepted.size, 1)
  fatal = true
  keys.length = 0
  accepted.clear()
  await assert.rejects(checkConcurrentRecordWrites(api, '/projects/p', 1), /busy/)
  assert.equal(keys.length, 1, 'an internal error must not be silently retried')
})
