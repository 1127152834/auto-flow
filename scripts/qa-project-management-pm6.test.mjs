import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  PM6_UI_STEPS,
  isOwnedPm6Workspace,
  parsePm6QaArgs,
  serviceAccountFixture,
} from './qa-project-management-pm6.mjs'

test('PM6 QA arguments keep automatic and manual modes explicit', () => {
  assert.deepEqual(parsePm6QaArgs([]), { manual: false, selfTest: false })
  assert.deepEqual(parsePm6QaArgs(['--manual']), { manual: true, selfTest: false })
  assert.throws(() => parsePm6QaArgs(['--prepare-only']), /unknown argument/)
})

test('PM6 workspace ownership requires both marker and containment', () => {
  const owner = '/tmp/autoflow-pm6-owner'
  const marker = { kind: 'pm6-project-management-qa', version: 1 }
  assert.equal(isOwnedPm6Workspace(`${owner}/workspace`, owner, marker), true)
  assert.equal(isOwnedPm6Workspace('/tmp/elsewhere', owner, marker), false)
  assert.equal(isOwnedPm6Workspace('/tmp/autoflow-pm6-owner-2/workspace', owner, marker), false)
  assert.equal(
    isOwnedPm6Workspace(`${owner}/workspace`, owner, { kind: 'other', version: 1 }),
    false,
  )
})

test('the QA service-account fixture only carries the frozen Google shape', () => {
  const fixture = JSON.parse(serviceAccountFixture())
  assert.equal(fixture.type, 'service_account')
  assert.equal(fixture.token_uri, 'https://oauth2.googleapis.com/token')
  assert.match(fixture.private_key, /^-----BEGIN PRIVATE KEY-----/)
  assert.deepEqual(Object.keys(fixture).sort(), [
    'client_email',
    'private_key',
    'project_id',
    'token_uri',
    'type',
  ])
})

test('PM6 steps name every user-visible stage of the management chain', () => {
  assert.deepEqual(PM6_UI_STEPS, [
    '真实界面新建项目与本地数据表、字段、记录',
    '真实界面连接 Google 账号（服务账号配置经主进程交接，无浏览器弹窗）',
    '真实界面绑定向导：读取工作表并检查、身份列选择、确认绑定',
    '拉取来源把远端行引入新数据代次',
    '本地编辑并推送，核验证据显示远端一致，替身远端单元格真的被写入',
    '远端改动公式列后拉取，只刷新公式列',
    '提交后响应丢失进入结果未知，核对结果得到确定结论且不重复写入',
    '解除绑定确认后取消不生效、确认后生效',
  ])
})

test('the runner drives business objects through the UI and labels its stand-ins', async () => {
  const source = await readFile(
    new URL('./qa-project-management-pm6.mjs', import.meta.url),
    'utf8',
  )
  assert.match(source, /click\('新建项目'\)/)
  assert.match(source, /click\('新建数据表'\)/)
  assert.match(source, /data-record-action="create"/)
  assert.match(source, /click\('连接 Google 账号'\)/)
  assert.match(source, /click\('读取工作表并检查'\)/)
  assert.match(source, /click\('确认绑定'\)/)
  assert.match(source, /click\('推送本地改动'\)/)
  assert.match(source, /click\('核对结果'\)/)
  assert.match(source, /click\('解除绑定'/)
  assert.match(source, /管理侧与本地契约已验证；真实 Google 端到端未执行/)
  // Business objects must come from the renderer, never from a seeded API call.
  assert.doesNotMatch(source, /api\([^\n]*\/projects[^\n]*method:\s*'POST'/)
  assert.doesNotMatch(source, /api\([^\n]*\/tables[^\n]*method:\s*'POST'/)
})

test('the QA sidecar swaps only the two declared ports and keeps a real bootstrap', async () => {
  const source = await readFile(
    new URL('../apps/backend/tests/qa/pm6_sidecar.py', import.meta.url),
    'utf8',
  )
  assert.match(source, /create_app\(\s*settings,\s*credential_store=/)
  assert.match(source, /google_tokens=FakeTokenTransport\(\)/)
  assert.match(source, /google_transports=lambda _token: transport/)
  assert.match(source, /lost_response/)
})
