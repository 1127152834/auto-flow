import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  PM4_V1_STEPS,
  isOwnedPm4Workspace,
  parsePm4QaArgs,
} from './qa-project-management-pm4.mjs'

test('PM4 QA arguments keep V1 automatic and preparation modes explicit', () => {
  assert.deepEqual(parsePm4QaArgs([]), { manual: false, prepareOnly: false, selfTest: false })
  assert.deepEqual(parsePm4QaArgs(['--manual', '--prepare-only']), { manual: true, prepareOnly: true, selfTest: false })
  assert.throws(() => parsePm4QaArgs(['--unknown']), /unknown argument/)
})

test('PM4 workspace ownership requires both marker and containment', () => {
  const owner = '/tmp/autoflow-pm4-owner'
  assert.equal(isOwnedPm4Workspace(`${owner}/workspace`, owner, { kind: 'pm4-v1-project-management-qa', version: 1 }), true)
  assert.equal(isOwnedPm4Workspace('/tmp/other', owner, { kind: 'pm4-v1-project-management-qa', version: 1 }), false)
  assert.equal(isOwnedPm4Workspace(`${owner}/workspace`, owner, { kind: 'wrong', version: 1 }), false)
})

test('V1 plan names every user-visible step and real fact', () => {
  assert.deepEqual(PM4_V1_STEPS, [
    'UI 创建项目',
    'UI 创建人员表、邮箱表、账号表及业务资料',
    'UI 创建自动化并配置两个独立必填输入',
    'UI 启动一个数据任务',
    'UI 查看不可变原始输入与显式数据写入',
    '只读 HTTP 核对人员不变、邮箱状态改变、账号只新增一次',
  ])
})

test('runner uses only UI for business object creation and labels fake executor boundary', async () => {
  const source = await readFile(new URL('./qa-project-management-pm4.mjs', import.meta.url), 'utf8')
  assert.match(source, /AUTOFLOW_PM4_QA/)
  assert.match(source, /executor:\s*'fake'/)
  assert.match(source, /browser:\s*'notExecuted'/)
  assert.match(source, /studio:\s*'notExecuted'/)
  assert.match(source, /click\('新建项目'\)/)
  assert.match(source, /click\('新建数据表'\)/)
  assert.match(source, /data-record-action="create"/)
  assert.match(source, /click\('新建自动化'\)/)
  assert.match(source, /click\('添加数据输入'\)/)
  assert.match(source, /click\('启动 1 个任务'\)/)
  assert.doesNotMatch(source, /api\([^\n]*\/(?:projects|tables|records|automations)[^\n]*method:\s*'POST'/)
  assert.match(source, /visualReview:\s*'pending'/)
  assert.match(source, /管理侧通过，真实执行核心接入待验收/)
})
