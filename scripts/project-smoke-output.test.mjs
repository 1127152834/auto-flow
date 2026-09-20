import assert from 'node:assert/strict'
import { access, mkdir, mkdtemp, rm, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { assertOutsideHistory, isWithinPath, redactSidecarLog } from './project-smoke-output.mjs'

test('history output guard resolves symlinks before any nested directory is created', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'autoflow-output-guard-'))
  try {
    const history = path.join(root, 'history')
    const alias = path.join(root, 'alias')
    await mkdir(history)
    await symlink(history, alias, 'junction')
    for (const target of [history, path.join(history, 'new'), alias, path.join(alias, 'new', 'nested')]) {
      await assert.rejects(assertOutsideHistory(history, target), /historical evidence/)
    }
    await assert.rejects(access(path.join(history, 'new')), { code: 'ENOENT' })
    await assertOutsideHistory(history, path.join(root, 'other', 'new'))
    await assertOutsideHistory(history, path.join(root, 'history-sibling'))
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test('containment handles Windows separators and sibling prefixes', () => {
  const root = 'C:\\repo\\history'
  assert.equal(isWithinPath(root, 'c:\\repo\\history\\run', path.win32), true)
  assert.equal(isWithinPath(root, 'C:/repo/history/run', path.win32), true)
  assert.equal(isWithinPath(root, root, path.win32), true)
  assert.equal(isWithinPath(root, 'C:\\repo\\history-new', path.win32), false)
  assert.equal(isWithinPath(root, 'D:\\repo\\history', path.win32), false)
})

test('failure logs retain the error while excluding startup metadata and service tokens', () => {
  const token = 'private-instance-token'
  const result = redactSidecarLog('x'.repeat(21000) + `\n AUTOFLOW_READY {"token":"${token}"}\nOperationalError: database is locked; token=${token}`, token)
  assert.ok(result.length <= 20_000)
  assert.ok(result.includes('OperationalError: database is locked'))
  assert.ok(!result.includes('AUTOFLOW_READY'))
  assert.ok(!result.includes(token))
})
