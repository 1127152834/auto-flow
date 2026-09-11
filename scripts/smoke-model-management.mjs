import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { startModelProviderFixture } from '../apps/desktop/tests/fixtures/model-provider-fixture.mjs'
import { launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const userData = await mkdtemp(join(tmpdir(), 'autoflow-model-smoke-'))
const qaDir = await mkdtemp(join(tmpdir(), 'autoflow-model-qa-'))
const fixture = await startModelProviderFixture()
let desktop

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  const { cdp } = desktop
  const sidecar = await waitFor(cdp, `(async () => {
    const status = await window.autoflow.getSidecarStatus()
    if (status.state !== 'ready') return null
    const response = await fetch(status.baseUrl + '/health', { headers: { 'x-autoflow-token': status.token } })
    const health = response.ok ? await response.json() : null
    return health?.status === 'ok' && health?.instanceId === status.instanceId ? status : null
  })()`, 'authenticated sidecar health')
  await waitFor(cdp, `document.body?.innerText.includes('模型管理')`, 'model management workspace', 30_000)
  await resizeAndCapture(cdp, 1440, 1024, join(qaDir, 'model-management-1440x1024.png'))

  await clickText(cdp, '添加供应商')
  await clickText(cdp, '自定义 OpenAI 兼容接口', true)
  await clickText(cdp, '下一步')
  await setValue(cdp, '#provider-name', 'Synthetic Local')
  await setValue(cdp, '#provider-url', fixture.baseUrl)
  await clickText(cdp, '测试连接')
  await waitFor(cdp, `document.body?.innerText.includes('连接测试成功')`, 'connection discovery')
  await clickAria(cdp, '选择 sample-chat')
  await clickText(cdp, '保存供应商和 1 个模型')
  await waitFor(cdp, `document.body?.innerText.includes('sample-chat')`, 'persisted discovered model')

  await waitFor(cdp, `!document.querySelector('[role=dialog]')`, 'wizard closed')
  await resizeAndCapture(cdp, 1440, 1024, join(qaDir, 'workspace-populated.png'))
  await resizeAndCapture(cdp, 800, 600, join(qaDir, 'workspace-small-populated.png'))
  await resizeAndCapture(cdp, 1440, 1024, join(qaDir, 'workspace-restored.png'))
  const saved = await api(sidecar, '/api/v1/model-providers')
  if (saved.total !== 1 || saved.items[0].models.length !== 1) throw new Error('discovered model not persisted')
  await clickRowButton(cdp, 'sample-chat', '测试')
  await waitFor(cdp, `document.body?.innerText.includes('OK')`, 'model generation result')
  await clickText(cdp, '添加模型')
  await setValue(cdp, 'input[aria-label="模型标识"]', 'manual-model')
  await setLabeledValue(cdp, '显示名称', 'Manual Model')
  await resizeAndCapture(cdp, 1440, 1024, join(qaDir, 'model-editor.png'))
  await clickText(cdp, '保存模型')
  await waitFor(cdp, `document.body?.innerText.includes('manual-model')`, 'manual model persistence')

  await clickAria(cdp, 'Manual Model 更多操作')
  await clickText(cdp, '编辑模型')
  await setLabeledValue(cdp, '显示名称', 'Manual Model Edited')
  await clickText(cdp, '保存修改')
  await waitFor(cdp, `document.body?.innerText.includes('Manual Model Edited')`, 'edited model persistence')
  await clickAria(cdp, 'Manual Model Edited 更多操作')
  await clickText(cdp, '删除模型')
  await clickText(cdp, '确认移除')
  await waitFor(cdp, `!document.body?.innerText.includes('manual-model')`, 'model deletion')

  await clickAria(cdp, '供应商更多操作')
  await clickText(cdp, '删除供应商')
  await clickText(cdp, '确认删除')
  await waitFor(cdp, `!document.body?.innerText.includes('Synthetic Local')`, 'provider deletion')

  const providers = await api(sidecar, '/api/v1/model-providers')
  if (providers.total !== 0) throw new Error(`provider deletion was not persisted: ${JSON.stringify(providers)}`)
  if (!fixture.requests.some(request => request.path === '/v1/models') || !fixture.requests.some(request => request.path === '/v1/chat/completions')) throw new Error('synthetic provider did not receive discovery and model-test calls')
  if (fixture.requests.some(request => request.authenticated)) throw new Error('empty-key compatible provider unexpectedly received Authorization')
  await resizeAndCapture(cdp, 920, 720, join(qaDir, 'model-management-small.png'))

  cdp.close()
  await stop(desktop.child)
  let exited = false
  for (let attempt = 0; attempt < 50; attempt++) {
    try { await fetch(`${sidecar.baseUrl}/health`, { signal: AbortSignal.timeout(500) }) }
    catch { exited = true; break }
    await wait(100)
  }
  if (!exited) throw new Error('sidecar survived desktop termination')
  console.log(`model management smoke passed; QA screenshots: ${qaDir}`)
} finally {
  desktop?.cdp.close()
  await stop(desktop?.child)
  await fixture.close()
  await rm(userData, { recursive: true, force: true })
}

async function evaluate(cdp, fn, ...args) {
  return cdp.evaluate(`(${fn})(${args.map(value => JSON.stringify(value)).join(',')})`)
}

async function clickText(cdp, text, prefix = false) {
  const clicked = await evaluate(cdp, (value, startsWith) => {
    const element = [...document.querySelectorAll('button,[role="menuitem"]')].find(node => startsWith ? node.textContent?.trim().startsWith(value) : node.textContent?.trim() === value)
    if (!element) return false
    element.scrollIntoView({ block: 'center' }); const rect = element.getBoundingClientRect(); return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
  }, text, prefix)
  if (!clicked) throw new Error(`control not found: ${text}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...clicked, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...clicked, button: 'left', clickCount: 1 })
  await wait(100)
}

async function clickAria(cdp, label) {
  const clicked = await evaluate(cdp, value => {
    const element = document.querySelector(`[aria-label="${CSS.escape(value)}"]`)
    if (!element) return false
    element.scrollIntoView({ block: 'center' }); const rect = element.getBoundingClientRect(); return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
  }, label)
  if (!clicked) throw new Error(`aria control not found: ${label}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...clicked, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...clicked, button: 'left', clickCount: 1 })
  await wait(100)
}

async function clickRowButton(cdp, modelKey, text) {
  const clicked = await evaluate(cdp, (key, value) => {
    const row = [...document.querySelectorAll('tr')].find(node => node.textContent?.includes(key))
    const button = row && [...row.querySelectorAll('button')].find(node => node.textContent?.trim() === value)
    if (!button) return false
    button.click(); return true
  }, modelKey, text)
  if (!clicked) throw new Error(`row control not found: ${modelKey}/${text}`)
}

async function setValue(cdp, selector, value) {
  const changed = await evaluate(cdp, (query, next) => {
    const element = document.querySelector(query)
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return false
    const setter = Object.getOwnPropertyDescriptor(element instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype, 'value').set
    setter.call(element, next); element.dispatchEvent(new Event('input', { bubbles: true })); return true
  }, selector, value)
  if (!changed) throw new Error(`input not found: ${selector}`)
}

async function setLabeledValue(cdp, label, value) {
  const selector = await evaluate(cdp, text => {
    const node = [...document.querySelectorAll('label')].find(item => item.textContent?.trim() === text)
    return node?.htmlFor ? `#${CSS.escape(node.htmlFor)}` : null
  }, label)
  if (!selector) throw new Error(`label not found: ${label}`)
  await setValue(cdp, selector, value)
}

async function api(sidecar, path) {
  const response = await fetch(`${sidecar.baseUrl}${path}`, { headers: { 'x-autoflow-token': sidecar.token } })
  if (!response.ok) throw new Error(`API verification failed: ${response.status} ${path}`)
  return response.json()
}

async function resizeAndCapture(cdp, width, height, path) {
  await cdp.command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
  await wait(250)
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}
