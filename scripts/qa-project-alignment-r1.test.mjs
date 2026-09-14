import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, mkdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { assertOwnedWorkspace } from './qa-project-alignment-r1.mjs'

test('R1 acceptance tools refuse paths outside the marked disposable root', async () => {
  const root = await mkdtemp(join(tmpdir(), 'autoflow-r1-test-'))
  try {
    await assert.rejects(assertOwnedWorkspace(root, root))
    await writeFile(join(root, '.r1-qa.json'), JSON.stringify({ kind:'autoflow-r1-qa', version:1 }))
    const workspace=join(root,'workspace-a');await mkdir(workspace)
    await assertOwnedWorkspace(root,workspace)
    await assert.rejects(assertOwnedWorkspace(root,tmpdir()))
  } finally { await rm(root,{recursive:true,force:true}) }
})
