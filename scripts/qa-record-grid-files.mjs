import { readFile, realpath, rm } from 'node:fs/promises'
import { basename, dirname, join } from 'node:path'
import { tmpdir } from 'node:os'

// Only the disposable workspace created by this QA tool may be removed.
export async function cleanupGridWorkspace(path) {
  const actual = await realpath(path), temporary = await realpath(tmpdir())
  if (dirname(actual) !== temporary || !basename(actual).startsWith('autoflow-grid-qa-')) throw new Error('不是本工具的临时工作区')
  const marker = JSON.parse(await readFile(join(actual, '.grid-qa.json'), 'utf8'))
  if (marker.kind !== 'autoflow-grid-qa' || marker.version !== 1 || typeof marker.evidence !== 'string') throw new Error('测试工作区标记无效')
  await rm(actual, { recursive: true })
  return marker.evidence
}
