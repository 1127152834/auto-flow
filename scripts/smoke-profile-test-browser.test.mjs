import assert from 'node:assert/strict'
import test from 'node:test'
import { chmod, mkdir, mkdtemp, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { findSessionDirectory, inspectPublicKernel, smokeOptions } from './smoke-profile-test-browser.mjs'

test('profile test browser smoke parses kernel and sidecar paths', () => {
  assert.deepEqual(smokeOptions([]), { kernelDirectory: undefined, executable: undefined })
  assert.deepEqual(smokeOptions(['--kernel-directory', '/kernel']), { kernelDirectory: '/kernel', executable: undefined })
  assert.deepEqual(smokeOptions(['--executable', '/sidecar', '--kernel-directory', '/kernel']), {
    kernelDirectory: '/kernel', executable: '/sidecar',
  })
  assert.throws(() => smokeOptions(['--kernel-directory']), /requires a path/)
  assert.throws(() => smokeOptions(['--kernel-directory', '--other']), /requires a path/)
  assert.throws(() => smokeOptions(['--executable']), /requires a path/)
  assert.throws(() => smokeOptions(['--other']), /unknown argument/)
})

test('profile test browser smoke validates a public kernel directory', async t => {
  const temporary = await mkdtemp(join(tmpdir(), 'autoflow-profile-test-browser-script-'))
  t.after(() => rm(temporary, { recursive: true, force: true }))
  const valid = join(temporary, 'chromium-145.0.7632.109.2')
  const platform = process.platform === 'win32' ? 'win32' : 'darwin'
  const executable = platform === 'win32' ? join(valid, 'chrome.exe') : join(valid, 'Chromium.app', 'Contents', 'MacOS', 'Chromium')
  await mkdir(join(executable, '..'), { recursive: true })
  await writeFile(executable, '#!/bin/sh\n')
  await chmod(executable, 0o755)
  assert.equal((await inspectPublicKernel(valid, platform)).version, '145.0.7632.109.2')

  const licensed = join(temporary, 'chromium-145.0.7632.109.2-pro')
  await mkdir(licensed)
  await assert.rejects(inspectPublicKernel(licensed, 'darwin'), /public edition/)

  const linked = join(temporary, 'chromium-146.0.1.1')
  await symlink(valid, linked, process.platform === 'win32' ? 'junction' : 'dir')
  await assert.rejects(inspectPublicKernel(linked, 'darwin'), /real directory/)
})

test('profile test browser smoke finds a session below the manager root', async t => {
  const temporary = await mkdtemp(join(tmpdir(), 'autoflow-profile-test-browser-sessions-'))
  t.after(() => rm(temporary, { recursive: true, force: true }))
  const expected = join(temporary, 'manager-root', 'session-id')
  await mkdir(expected, { recursive: true })
  assert.equal(await findSessionDirectory(temporary, 'session-id'), expected)
  assert.equal(await findSessionDirectory(temporary, 'missing'), undefined)
})

test('Windows kernels do not require POSIX executable bits', async t => {
  const temporary = await mkdtemp(join(tmpdir(), 'autoflow-windows-kernel-'))
  t.after(() => rm(temporary, { recursive: true, force: true }))
  const directory = join(temporary, 'chromium-145.0.7632.109.2')
  await mkdir(directory)
  await writeFile(join(directory, 'chrome.exe'), 'binary', { mode: 0o644 })
  assert.equal((await inspectPublicKernel(directory, 'win32')).version, '145.0.7632.109.2')
})
