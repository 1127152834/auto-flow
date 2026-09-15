import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { test } from 'node:test'
import { promisify } from 'node:util'

const exec = promisify(execFile)
const script = new URL('./qa-project-management-pm3.mjs', import.meta.url)

test('self-test accepts only a marker-owned workspace below its owner', async () => {
  const { stdout } = await exec(process.execPath, [script.pathname, '--self-test'])
  assert.match(stdout, /qa helper self-test passed/)
})

test('arguments reject missing kernel paths before launching Electron', async () => {
  await assert.rejects(
    exec(process.execPath, [script.pathname, '--kernel-directory']),
    error => error.stderr.includes('--kernel-directory requires a path'),
  )
})

test('arguments reject unknown switches before launching Electron', async () => {
  await assert.rejects(
    exec(process.execPath, [script.pathname, '--write-main-workspace']),
    error => error.stderr.includes('unknown argument: --write-main-workspace'),
  )
})

test('scenario selection is validated before any workspace or Electron launch', async () => {
  const { stdout } = await exec(process.execPath, [script.pathname, '--self-test', '--scenario', 'stop'])
  assert.match(stdout, /qa helper self-test passed/)
  await assert.rejects(
    exec(process.execPath, [script.pathname, '--scenario', 'invented']),
    error => error.stderr.includes('--scenario must be success, failure, stop, force-stop, recovery, restart, or isolation'),
  )
})
