import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  PM7_FAULT_KINDS,
  PM7_STEPS,
  isOwnedPm7Workspace,
  parsePm7QaArgs,
} from './qa-project-management-pm7.mjs'

test('PM7 QA arguments keep manual, preparation and cleanup modes explicit', () => {
  assert.deepEqual(parsePm7QaArgs([]), { manual: false, prepareOnly: false, selfTest: false, cleanupOnly: false, workspace: undefined, inject: [] })
  assert.deepEqual(parsePm7QaArgs(['--manual', '--prepare-only']), { manual: true, prepareOnly: true, selfTest: false, cleanupOnly: false, workspace: undefined, inject: [] })
  assert.deepEqual(parsePm7QaArgs(['--cleanup-only', '--workspace=/tmp/pm7']), { manual: false, prepareOnly: false, selfTest: false, cleanupOnly: true, workspace: '/tmp/pm7', inject: [] })
  assert.deepEqual(parsePm7QaArgs(['--manual', '--inject=statistics-ttl', '--inject=service-restart']).inject, ['statistics-ttl', 'service-restart'])
  assert.throws(() => parsePm7QaArgs(['--unknown']), /unknown argument/)
  assert.throws(() => parsePm7QaArgs(['--inject=not-a-fault']), /unknown fault injection/)
})

test('PM7 workspace ownership requires both marker and containment', () => {
  const owner = '/tmp/autoflow-pm7-owner'
  assert.equal(isOwnedPm7Workspace(`${owner}/workspace`, owner, { kind: 'pm7-project-management-qa', version: 1, runId: 'r1' }), true)
  assert.equal(isOwnedPm7Workspace('/tmp/other', owner, { kind: 'pm7-project-management-qa', version: 1, runId: 'r1' }), false)
  assert.equal(isOwnedPm7Workspace(`${owner}/workspace`, owner, { kind: 'pm4-v1-project-management-qa', version: 1 }), false)
  assert.equal(isOwnedPm7Workspace(`${owner}/workspace`, owner, { kind: 'pm7-project-management-qa', version: 2, runId: 'r1' }), false)
})

test('every PM7 end-to-end step and fault injection is named', () => {
  assert.equal(PM7_STEPS.length, 6)
  assert.ok(PM7_STEPS.every(step => /^E2E-[1-6]/.test(step)))
  assert.deepEqual([...PM7_FAULT_KINDS].sort(), [
    'executor-fail',
    'executor-pause',
    'executor-resume',
    'followup-conflict',
    'late-event',
    'overview-read-failure',
    'response-loss',
    'statistics-read-failure',
    'statistics-ttl',
  ])
})

test('runner drives the product through the renderer and labels the executor boundary', async () => {
  const source = await readFile(new URL('./qa-project-management-pm7.mjs', import.meta.url), 'utf8')
  assert.match(source, /AUTOFLOW_QA_SIDECAR_MODULE = 'tests\.qa\.pm7_sidecar'/)
  assert.match(source, /executor:\s*'isolatedQaExecutor'/)
  assert.match(source, /browser:\s*'notExecuted'/)
  assert.match(source, /studio:\s*'notExecuted'/)
  assert.match(source, /click\('新建项目'\)/)
  assert.match(source, /click\('新建数据表'\)/)
  assert.match(source, /data-record-action="create"/)
  assert.match(source, /click\('新建自动化'\)/)
  assert.match(source, /click\('添加数据输入'\)/)
  assert.match(source, /视觉|visualReview:\s*'pending'/)
  assert.match(source, /管理侧通过，真实执行核心接入待验收/)
  assert.match(source, /01-overview\/001/)
  assert.match(source, /04-statistics\/001/)
  // 证据引用必须指向真实对应的画板：任务详情是 005 任务日志，下钻是 007 冻结下钻。
  assert.match(source, /03-runs\/005-task-log-510347\.png/)
  assert.match(source, /04-statistics\/007-frozen-drilldown-00b0db\.png/)
  assert.ok(source.includes('runs\\/frozen'), '下钻证据必须断言冻结结果集的运行记录地址')
})

test('fault injection only exists in the QA sidecar and never in production modules', async () => {
  const sidecar = await readFile(new URL('../apps/backend/tests/qa/pm7_sidecar.py', import.meta.url), 'utf8')
  assert.match(sidecar, /include_in_schema=False/)
  for (const kind of PM7_FAULT_KINDS) assert.ok(sidecar.includes(kind), `sidecar must implement ${kind}`)
  assert.match(sidecar, /class ResponseDrop/)
  const statistics = await readFile(new URL('../apps/backend/src/autoflow/application/projects/statistics.py', import.meta.url), 'utf8')
  assert.doesNotMatch(statistics, /pm7|PM7/)
})
