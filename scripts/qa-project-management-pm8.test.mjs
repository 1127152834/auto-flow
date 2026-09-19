import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  PM8_FAULT_KINDS,
  PM8_MANUAL_FAULT_KINDS,
  PM8_STEPS,
  isOwnedPm8Workspace,
  parsePm8QaArgs,
} from './qa-project-management-pm8.mjs'

test('PM8 QA arguments keep manual, preparation and cleanup modes explicit', () => {
  assert.deepEqual(parsePm8QaArgs([]), { manual: false, prepareOnly: false, selfTest: false, cleanupOnly: false, workspace: undefined, inject: [] })
  assert.deepEqual(parsePm8QaArgs(['--manual', '--prepare-only']), { manual: true, prepareOnly: true, selfTest: false, cleanupOnly: false, workspace: undefined, inject: [] })
  assert.deepEqual(parsePm8QaArgs(['--cleanup-only', '--workspace=/tmp/pm8']), { manual: false, prepareOnly: false, selfTest: false, cleanupOnly: true, workspace: '/tmp/pm8', inject: [] })
  assert.deepEqual(parsePm8QaArgs(['--prepare-only', '--inject=expire-lifecycle-impact', '--inject=service-restart']).inject, ['expire-lifecycle-impact', 'service-restart'])
  assert.deepEqual(parsePm8QaArgs(['--self-test']), { manual: false, prepareOnly: false, selfTest: true, cleanupOnly: false, workspace: undefined, inject: [] })
  assert.throws(() => parsePm8QaArgs(['--unknown']), /unknown argument/)
  assert.throws(() => parsePm8QaArgs(['--inject=not-a-fault']), /unknown fault injection/)
})

test('PM8 workspace ownership requires both marker and containment', () => {
  const owner = '/tmp/autoflow-pm8-owner'
  assert.equal(isOwnedPm8Workspace(`${owner}/workspace`, owner, { kind: 'pm8-project-management-qa', version: 1, runId: 'r1' }), true)
  assert.equal(isOwnedPm8Workspace('/tmp/other', owner, { kind: 'pm8-project-management-qa', version: 1, runId: 'r1' }), false)
  assert.equal(isOwnedPm8Workspace(`${owner}/workspace`, owner, { kind: 'pm6-project-management-qa', version: 1 }), false)
  assert.equal(isOwnedPm8Workspace(`${owner}/workspace`, owner, { kind: 'pm8-project-management-qa', version: 2, runId: 'r1' }), false)
})

test('every PM8 end-to-end step and fault injection is named', () => {
  assert.equal(PM8_STEPS.length, 7)
  assert.ok(PM8_STEPS.every(step => /^E2E-[1-7]/.test(step)))
  assert.deepEqual([...PM8_FAULT_KINDS].sort(), ['expire-lifecycle-impact', 'lifecycle-response-loss'])
})

test('manual injections expose the executor faults the hand-test plan needs', () => {
  assert.deepEqual([...PM8_MANUAL_FAULT_KINDS].sort(), ['executor-fail', 'executor-pause', 'executor-resume'])
  assert.deepEqual(parsePm8QaArgs(['--manual', '--inject=executor-pause', '--inject=executor-resume']).inject, ['executor-pause', 'executor-resume'])
  assert.deepEqual(parsePm8QaArgs(['--inject=executor-fail']).inject, ['executor-fail'])
  assert.throws(() => parsePm8QaArgs(['--inject=executor-nope']), /unknown fault injection/)
})

test('runner drives the product through the renderer and labels the executor boundary', async () => {
  const source = await readFile(new URL('./qa-project-management-pm8.mjs', import.meta.url), 'utf8')
  assert.match(source, /AUTOFLOW_QA_SIDECAR_MODULE = 'tests\.qa\.pm8_sidecar'/)
  assert.match(source, /executor:\s*'isolatedQaExecutor'/)
  assert.match(source, /browser:\s*'notExecuted'/)
  assert.match(source, /studio:\s*'notExecuted'/)
  assert.match(source, /click\('新建项目'\)/)
  assert.match(source, /click\('新建数据表'\)/)
  assert.match(source, /data-record-action="create"/)
  assert.match(source, /click\('新建自动化'\)/)
  assert.match(source, /click\('添加数据输入'\)/)
  assert.match(source, /管理侧通过，真实执行核心接入待验收/)
  assert.match(source, /visualReview:\s*'pending'/)
  // 证据引用必须指向真实对应的画板：归档确认、归档只读与删除确认各有独立原图。
  assert.match(source, /02-automation\/004-delete-confirm-54c904\.png/)
  assert.match(source, /02-automation\/010-archived-readonly-46a6a4\.png/)
  assert.match(source, /03-runs\/004-batch-detail-approved-459f25\.png/)
  // 生命周期退回必须以真实幂等身份重发，不能在响应丢失后换键。
  assert.match(source, /lifecycle-response-loss/)
  assert.match(source, /同一幂等身份不得产生第二条归档事实/)
})

test('lifecycle fault injection only exists in the QA sidecar and never in production modules', async () => {
  const sidecar = await readFile(new URL('../apps/backend/tests/qa/pm8_sidecar.py', import.meta.url), 'utf8')
  assert.match(sidecar, /include_in_schema=False/)
  for (const kind of PM8_FAULT_KINDS) assert.ok(sidecar.includes(kind), `sidecar must implement ${kind}`)
  assert.match(sidecar, /tests\.qa\.pm7_sidecar/)
  const lifecycle = await readFile(new URL('../apps/backend/src/autoflow/application/projects/lifecycle.py', import.meta.url), 'utf8')
  assert.doesNotMatch(lifecycle, /pm8|PM8/)
})
