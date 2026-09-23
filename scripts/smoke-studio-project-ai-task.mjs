import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/project-integration')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-project-ai-task-electron-'))
const workspace = await mkdtemp(join(tmpdir(), 'autoflow-project-ai-task-'))
const calls = []
const model = createServer(async (request, response) => {
  let raw = ''
  for await (const chunk of request) raw += chunk
  const body = raw ? JSON.parse(raw) : {}
  if (request.url === '/v1/models') return json(response, { data: [{ id: 'default-model' }, { id: 'explicit-model' }] })
  if (request.url !== '/v1/chat/completions') return json(response, { error: 'not found' }, 404)
  calls.push({ model: body.model, prompt: JSON.stringify(body.messages ?? []) })
  return json(response, { choices: [{ message: { content: body.model === 'default-model' ? '项目默认模型响应' : '项目覆盖模型响应' } }] })
})
await new Promise((resolve, reject) => { model.once('error', reject); model.listen(0, '127.0.0.1', resolve) })
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
const checks = []
let desktop, main, studio

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const baseUrl = `http://127.0.0.1:${model.address().port}/v1`
  const defaultProvider = await connectModel(runtime, baseUrl, '项目 AI 默认模型', 'default-model')
  const explicitProvider = await connectModel(runtime, baseUrl, '项目 AI 覆盖模型', 'explicit-model')

  await click(main, '项目', 'a, button')
  await click(main, '新建项目')
  await input(main, '#project-name', '项目 AI 任务正式验收')
  await click(main, '创建项目')
  await waitFor(main, "document.body?.innerText.includes('项目 AI 任务正式验收')", 'project created')
  if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, '项目 AI 任务正式验收', '[role="button"],button')
  await waitForProjectPage(main)
  const projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
  assert.ok(projectId)
  const project = await api(runtime, `/v1/projects/${projectId}`)
  await api(runtime, `/v1/projects/${projectId}`, { method: 'PATCH', body: {
    expectedManagementRevision: project.managementRevision,
    defaultResources: { ...project.defaultResources, modelProviderId: defaultProvider.id },
  } })
  await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
  checks.push('主应用模型管理建立两个受控模型；项目默认提供方通过公开项目接口设置为测试前置数据')

  await click(main, '工作流工作台')
  const target = await until(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target')
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'Studio ready', 30_000)
  assert.equal(await studio.evaluate("new URL(location.href).searchParams.get('projectId')"), projectId)
  await click(studio, '新建')
  await input(studio, 'input[placeholder="工作流名称"]', '项目 AI 摘要任务')
  const pane = await point(studio, '.react-flow__pane')
  for (const type of ['mousePressed', 'mouseReleased']) await studio.command('Input.dispatchMouseEvent', { type, ...pane, button: 'right', clickCount: 1 })
  await input(studio, 'input[placeholder="搜索模块（支持拼音）"]', 'AI文本摘要')
  await click(studio, 'AI文本摘要', '[role="button"]')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length===1", 'AI node')
  await input(studio, 'textarea[placeholder^="要处理的文本"]', '项目任务原文')
  await input(studio, 'input[placeholder="结果变量名"]', 'summary')
  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: 项目 AI 摘要任务')", 'workflow saved')
  const saved = (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === '项目 AI 摘要任务')
  assert.ok(saved && saved.projectId === projectId)
  assert.equal(saved.nodes.length, 1)
  assert.ok(!saved.nodes[0].data.modelId && !saved.nodes[0].data.config?.modelId)
  checks.push('正式 Studio 真实界面添加 AI 摘要、填写参数并保存项目工作流；继承模型未写入文档')

  await closeStudio(desktop)
  studio.close(); studio = undefined
  await waitForNoStudio(desktop)
  await click(main, '新建自动化')
  await input(main, '[aria-label="自动化名称"]', '项目 AI 摘要自动化')
  await click(main, '关联工作流', '[role="combobox"]')
  await click(main, '项目 AI 摘要任务', '[role="option"]')
  await click(main, '保存配置')
  await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'automation created')

  const first = await runBatch(runtime, main, projectId, 'default-model', '项目默认模型响应')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].model, 'default-model')
  checks.push('项目 UI 启动真实受管 worker；继承默认模型调用受控 HTTP 服务，输出与日志持久化并显示在任务页')

  await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
  await click(main, '打开自动化 项目 AI 摘要自动化')
  await click(main, '打开 Studio')
  const nextTarget = await until(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'reopened Studio')
  studio = await connectCdp(nextTarget.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length===1", 'restored AI node')
  await click(studio, '', '.react-flow__node')
  await chooseModel(studio, '项目 AI 覆盖模型', explicitProvider.models[0].id)
  await click(studio, '保存')
  const updated = await until(async () => { const doc = await api(runtime, `/workflows/${saved.id}?projectId=${projectId}`); return doc.revision > saved.revision ? doc : null }, 'explicit model saved')
  assert.equal(updated.nodes[0].data.config?.modelId ?? updated.nodes[0].data.modelId, explicitProvider.models[0].id)
  await closeStudio(desktop)
  studio.close(); studio = undefined
  await waitForNoStudio(desktop)
  const second = await runBatch(runtime, main, projectId, 'explicit-model', '项目覆盖模型响应')
  assert.deepEqual(calls.map(item => item.model), ['default-model', 'explicit-model'])
  assert.ok(calls.every(item => item.prompt.includes('项目任务原文')))
  assert.deepEqual(execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser|--project-workflow-worker/.test(line)), [])
  checks.push('节点显式覆盖模型后再次真实运行，仅第二次请求使用覆盖模型；两次任务输出独立持久化')

  const packageHashes = desktop.packaged ? await hashes(process.argv[process.argv.indexOf('--executable') + 1]) : null
  const report = {
    evidenceId: 'BE-project-ai-task-formal-electron', result: 'passed', checkedAt: new Date().toISOString(),
    platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build',
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    projectId, workflowId: saved.id, batchIds: [first.batchId, second.batchId], taskIds: [first.taskId, second.taskId],
    modelRequests: calls, checks, packageHashes,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, model: 'local controlled OpenAI-compatible HTTP fixture', interaction: 'formal Electron CDP mouse/keyboard; API only fixture setup and evidence reads' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await screenshot(studio, 'failure-studio.png').catch(() => {})
  if (main) await screenshot(main, 'failure-main.png').catch(() => {})
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ result: 'failed', checks, error: String(error.stack ?? error) }, null, 2) + '\n')
  console.error(evidenceDir)
  throw error
} finally {
  studio?.close(); main?.close()
  if (desktop) await stop(desktop.child)
  model.closeAllConnections()
  await new Promise(resolve => model.close(resolve))
  await rm(workspace, { recursive: true, force: true })
}

async function connectModel(runtime, baseUrl, name, key) {
  return api(runtime, '/v1/model-providers/connect', { method: 'POST', body: {
    provider: { name, presetId: 'custom-openai-compatible', providerKind: 'openai-compatible', baseUrl, apiKey: '', enabled: true, description: '项目 AI 正式验收' },
    selectedModels: [{ modelKey: key, displayName: name, tagsJson: ['chat'], contextWindow: 32768, enabled: true, description: '' }],
  } })
}

async function runBatch(runtime, page, projectId, expectedModel, expectedResult) {
  await click(page, '启动运行')
  await waitFor(page, "document.body?.innerText.includes('启动自动化')", 'batch launch dialog')
  await click(page, '启动 1 个任务')
  await waitFor(page, "document.body?.innerText.includes('本批次任务')", 'batch detail', 30_000)
  const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
  const terminal = await until(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'AI batch terminal', 90_000)
  assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify(terminal))
  const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
  const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=20`)
  assert.ok(outputs.items.some(item => item.name === 'summary' && JSON.stringify(item.value).includes(expectedResult)), JSON.stringify(outputs))
  const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=20`)
  assert.equal(attempts.total, 1)
  assert.equal(attempts.items[0].status, 'succeeded')
  const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?afterSequence=0&pageSize=20`)
  assert.ok(logs.items.length > 0)
  await click(page, '查看任务')
  await click(page, '日志', '[role="tab"]')
  await waitFor(page, "document.body?.innerText.includes('AI文本摘要')", 'AI node log rendered')
  await click(page, '输入与输出', '[role="tab"]')
  await waitFor(page, `document.body?.innerText.includes(${JSON.stringify(expectedResult)})`, 'AI output rendered')
  await screenshot(page, `batch-${expectedModel}.png`)
  return { batchId: batch.batchId, taskId: task.taskId }
}

function json(response, body, status = 200) {
  const payload = Buffer.from(JSON.stringify(body))
  response.writeHead(status, { 'content-type': 'application/json', 'content-length': payload.length })
  response.end(payload)
}

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} ${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function until(read, label, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) }
  throw new Error(`timed out waiting for ${label}`)
}

async function point(page, selector, text = '') {
  return waitFor(page, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, text || selector)
}

async function click(page, text, selector = 'button') {
  const p = await point(page, selector, text)
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...p, button: 'left', clickCount: 1 })
  await wait(100)
}

async function input(page, selector, value) {
  const p = await point(page, selector)
  for (const type of ['mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...p, button: 'left', clickCount: 3 })
  await page.command('Input.insertText', { text: value })
  for (const type of ['keyDown', 'keyUp']) await page.command('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
}

async function chooseModel(page, label, modelId) {
  await click(page, 'AI 模型设置', 'summary')
  const selector = `(()=>{const e=[...document.querySelectorAll('label')].find(x=>x.textContent.includes('主应用模型'))?.parentElement?.querySelector('[role="combobox"]');if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`
  const p = await waitFor(page, selector, 'model select')
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...p, button: 'left', clickCount: 1 })
  await click(page, label, '[role="option"]')
  await waitFor(page, `document.querySelector('[role="combobox"][data-state="closed"]') && [...document.querySelectorAll('[role="combobox"]')].some(e=>e.textContent.includes(${JSON.stringify(label)}))`, 'model selected')
  assert.ok(modelId)
}

async function closeStudio(desktop) {
  assert.equal(process.platform, 'darwin')
  execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${desktop.child.pid})`, '-e', 'click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")', '-e', 'end tell', '-e', 'end tell'])
}

async function waitForNoStudio(desktop) {
  await until(async () => !(await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).some(item => item.type === 'page' && item.url.includes('studio.html')), 'normal Studio close')
}

async function screenshot(page, name) {
  const { data } = await page.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(evidenceDir, name), data, 'base64')
}

async function hashes(executable) {
  const resources = resolve(dirname(resolve(executable)), '../Resources')
  const files = [join(resources, 'app.asar'), join(resources, 'backend', 'autoflow-backend')]
  return Object.fromEntries(await Promise.all(files.map(async file => [file.split('/').at(-1), createHash('sha256').update(await readFile(file)).digest('hex')])))
}
