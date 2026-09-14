import assert from 'node:assert/strict'
import { access, mkdir, mkdtemp, rm, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { assertOutsideHistory, isWithinPath } from './project-smoke-output.mjs'

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
