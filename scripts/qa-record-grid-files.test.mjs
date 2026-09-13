import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { cleanupGridWorkspace } from './qa-record-grid-files.mjs'

test('cleanup rejects an unmarked or wrongly marked workspace', async () => {
 const path=await mkdtemp(join(tmpdir(),'autoflow-grid-qa-'))
 try {
  await assert.rejects(cleanupGridWorkspace(path))
  await writeFile(join(path,'.grid-qa.json'),JSON.stringify({kind:'business',version:1}))
  await assert.rejects(cleanupGridWorkspace(path));assert.ok(await stat(path))
 } finally { await rm(path,{recursive:true,force:true}) }
})
test('cleanup removes only a marked temporary workspace and returns the preserved evidence path', async () => {
 const path=await mkdtemp(join(tmpdir(),'autoflow-grid-qa-'))
 await writeFile(join(path,'.grid-qa.json'),JSON.stringify({kind:'autoflow-grid-qa',version:1,evidence:'/evidence/retained'}))
 assert.equal(await cleanupGridWorkspace(path),'/evidence/retained')
 await assert.rejects(stat(path))
})
