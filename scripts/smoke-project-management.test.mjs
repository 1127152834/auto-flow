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
