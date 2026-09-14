import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { main } from './qa-project-alignment-r1.mjs'
import { run } from './qa-project-alignment-r2.mjs'

test('R2 wrapper reuses the exported R1 harness',async()=>{
  assert.equal(typeof main,'function');assert.equal(typeof run,'function')
  const wrapper=await readFile(new URL('./qa-project-alignment-r2.mjs',import.meta.url),'utf8')
  assert.match(wrapper,/main\(\{\.\.\.options,recordPages:true\}\)/);assert.doesNotMatch(wrapper,/launchElectron|connectCdp|mkdtemp/)
})

test('record-pages mode records required evidence levels and leaves visual review pending',async()=>{
  const source=await readFile(new URL('./qa-project-alignment-r1.mjs',import.meta.url),'utf8')
  for(const id of ['r2-create-normal','r2-create-dirty','r2-create-saving','r2-detail-loading','r2-detail-normal','r2-edit-normal','r2-edit-dirty','r2-edit-validation','r2-edit-leave-confirm','r2-detail-404','r2-detail-read-error','r2-detail-200'])assert.match(source,new RegExp(id))
  assert.match(source,/visualReview:'pending'/);assert.match(source,/delayed-real-record-write-response/);assert.match(source,/stateSource:'direct-route'/);assert.match(source,/r2-select-geometry\.json/)
  assert.match(source,/wrapperSha256/);assert.match(source,/options:\{recordPages,manual,visualDirectory\}/);assert.match(source,/checkScreenshotMap/)
  assert.match(source,/statusRevision>beforeStatus\.statusRevision/);assert.match(source,/statusId===null&&value\.statusRevision>assigned\.statusRevision/)
  assert.match(source,/\{w:720,h:512,dpr:2\}/);assert.match(source,/assert\.notEqual\(await renderer\.evaluate\(focusSignature\),beforeTab\)/)
})
