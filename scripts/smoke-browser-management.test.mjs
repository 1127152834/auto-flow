import assert from 'node:assert/strict'
import test from 'node:test'
import { join } from 'node:path'

import { kernelExecutablePath, smokeMode } from './smoke-browser-management.mjs'

test('browser management smoke accepts an explicit packaged sidecar', () => {
  assert.deepEqual(smokeMode([]), { executable: undefined })
  assert.deepEqual(smokeMode(['--executable', '/artifact']), { executable: '/artifact' })
  assert.throws(() => smokeMode(['--executable']), /requires a path/)
  assert.throws(() => smokeMode(['--executable', '--other']), /requires a path/)
})

test('browser management smoke creates the platform kernel layout', () => {
  assert.equal(kernelExecutablePath('/kernel', 'win32'), join('/kernel', 'chrome.exe'))
  assert.equal(
    kernelExecutablePath('/kernel', 'darwin'),
    join('/kernel', 'Chromium.app', 'Contents', 'MacOS', 'Chromium'),
  )
  assert.throws(() => kernelExecutablePath('/kernel', 'linux'), /does not support linux/)
})
