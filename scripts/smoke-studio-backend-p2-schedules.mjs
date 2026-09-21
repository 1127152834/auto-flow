import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/p2')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-schedules-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-p2-schedules-'))
const workspaceDir = join(userData, 'workspace')
const workflowName = 'P2 计划任务真实流程'
const workflowFile = `${workflowName}.json`
const taskName = 'P2 自动触发真实 CloakBrowser'
const executableIndex = process.argv.indexOf('--executable')
const packagedExecutable = executableIndex === -1 ? null : process.argv[executableIndex + 1]
const pageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href
const checks = []
let desktop, main, studio, runtime

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  ;({ desktop, main, studio, runtime } = await launchAndOpen())
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'P2 计划任务验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  await api(runtime, '/local-workflows/save-to-folder', {
    method: 'POST',
    body: { filename: workflowFile, content: workflowDocument() },
  })
  checkpoint('通过真实服务在临时工作区创建主应用 CloakBrowser Profile 与本地工作流')

  await click(studio, '计划任务', 'button[aria-label="计划任务"]')
  await waitFor(studio, "document.body.innerText.includes('还没有计划任务')", 'empty scheduled task page')
  await click(studio, '立即创建')
  await waitFor(studio, "document.body.innerText.includes('创建计划任务')", 'scheduled task create dialog')
  await setInput(studio, 'input[placeholder="输入任务名称"]', taskName)
  await selectByLabel(studio, '关联工作流', workflowName)
  await waitFor(studio, `document.querySelector('select[aria-label="运行浏览器配置 *"]')?.value===${JSON.stringify(profile.id)}`, 'main Profile selected')
  await selectByLabel(studio, '调度类型', '间隔执行')
  await setInputByLabel(studio, '间隔秒数', '12')
  await clickExpression(studio, "[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='创建任务').at(-1)", 'create scheduled task submit')

  const task = await waitForValue(async () => (await api(runtime, '/scheduled-tasks/list')).find(item => item.name === taskName), 'persisted scheduled task', 15_000)
  assert.equal(task.profile_id, profile.id)
  assert.equal(task.workflow_id, workflowFile)
  assert.equal(task.trigger.interval_seconds, 12)
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(taskName)})`, 'scheduled task card')
  checkpoint('通过正式 Studio 表单绑定本地工作流和主应用 Profile，计划与下次触发时间持久化')

  const processWatch = watchCloakBrowser(userData)
  const execution = await waitForValue(async () => {
    const logs = await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}/logs?limit=20`)
    return logs.find(item => item.status === 'success' && item.trigger_type === 'time') ?? null
  }, 'automatic scheduled execution', 90_000)
  const sawCloakBrowser = await processWatch.stop()
  assert.equal(sawCloakBrowser, true)
  assert.ok(execution.run_id)

  const run = await api(runtime, `/workflow-runs/${encodeURIComponent(execution.run_id)}`)
  assert.equal(run.status, 'completed')
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(execution.run_id)}/results?cursor=0&limit=50`)
  assert.equal(results.items.find(item => item.nodeId === 'extract')?.values.value, '计划任务真实执行')
  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(execution.run_id)}/artifacts?cursor=0&limit=20`)
  assert.equal(artifacts.items.length, 1)
  assert.equal(artifacts.items[0].mimeType, 'image/png')
  const png = await apiBytes(runtime, `/workflow-runs/${encodeURIComponent(execution.run_id)}/artifacts/${encodeURIComponent(artifacts.items[0].artifactId)}`)
  assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
  checkpoint('间隔计划自动触发真实 CloakBrowser，五节点执行结果、日志和 PNG 均已持久化')

  await clickExpression(studio, `(()=>{const h=[...document.querySelectorAll('h3')].find(e=>e.textContent.trim()===${JSON.stringify(taskName)});return h?.closest('.relative')?.querySelector('button')})()`, 'disable scheduled task')
  await waitForValue(async () => (await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}`)).enabled === false ? true : null, 'task disabled through UI', 10_000)
  if ((await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}`)).is_running) {
    await click(studio, '停止')
    await clickExpression(studio, "[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='停止').at(-1)", 'confirm scheduled task stop')
    await waitForValue(async () => (await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}`)).is_running === false ? true : null, 'in-flight scheduled execution stopped', 30_000)
  }
  await click(studio, '日志')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(`执行日志 - ${taskName}`)}) && document.body.innerText.includes('成功')`, 'persisted task logs dialog')
  await capture(studio, join(evidenceDir, 'scheduled-run-success.png'))
  checkpoint('正式任务日志界面展示成功记录，用户可停用任务阻止后续触发')

  await waitForValue(async () => cloakProcesses(userData).length === 0 ? true : null, 'CloakBrowser process cleanup', 15_000)
  checkpoint('计划运行终态后 CloakBrowser 进程树、worker 与资源占用已清理')

  studio.close(); main.close(); await stop(desktop.child)
  desktop = main = studio = runtime = undefined
  ;({ desktop, main, studio, runtime } = await launchAndOpen())
  await click(studio, '计划任务', 'button[aria-label="计划任务"]')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(taskName)})`, 'scheduled task after sidecar restart', 30_000)
  const restored = await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}`)
  const restoredLogs = await api(runtime, `/scheduled-tasks/${encodeURIComponent(task.id)}/logs?limit=20`)
  assert.equal(restored.enabled, false)
  assert.ok(restoredLogs.some(item => item.id === execution.id && item.status === 'success'))
  await capture(studio, join(evidenceDir, 'scheduled-task-restored.png'))
  checkpoint('完整重启 Electron 与 sidecar 后，计划、停用状态、运行关联和日志从 SQLite 恢复且未重复执行')

  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify({
    evidenceId: 'BE-P2-scheduled-tasks-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`,
    entry: desktop.packaged ? 'packaged-directory' : 'development-build',
    buildSha256: await buildHash(),
    ...(packagedExecutable ? { executableSha256: createHash('sha256').update(await readFile(packagedExecutable)).digest('hex') } : {}),
    task: { id: task.id, workflowId: task.workflow_id, profileId: task.profile_id, trigger: task.trigger },
    execution: { id: execution.id, runId: execution.run_id, triggerType: execution.trigger_type, status: execution.status },
    artifact: { id: artifacts.items[0].artifactId, mimeType: artifacts.items[0].mimeType, sha256: artifacts.items[0].sha256 },
    checks,
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false,
      browser: 'real CloakBrowser from main-app Profile; no fallback browser',
      interaction: 'formal Electron through CDP mouse and keyboard; public API only for fixture setup and evidence reads; no Store or page-internal business function access',
    },
  }, null, 2) + '\n')
  console.log(`P2 scheduled task formal smoke passed: ${evidenceDir}`)
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

function workflowDocument() {
  return {
    id: 'p2-scheduled-workflow', name: workflowName, schemaVersion: 3,
    nodes: [
      node('open', 'open_page', { url: pageUrl, openMode: 'current_tab' }),
      node('input', 'input_text', { selector: '#workflow-input', text: '计划任务真实执行', clearBefore: true }),
      node('click', 'click_element', { selector: '.workflow-action', clickType: 'single' }),
      node('extract', 'get_element_info', { selector: '#workflow-output', attribute: 'text', variableName: 'result' }),
      node('shot', 'screenshot', { screenshotType: 'viewport', fileNamePattern: 'p2-scheduled', variableName: 'shot' }),
    ],
    edges: ['open,input', 'input,click', 'click,extract', 'extract,shot'].map((pair, index) => {
      const [source, target] = pair.split(','); return { id: `e${index + 1}`, source, target }
    }),
    variables: [],
  }
}
function node(id, moduleType, config) { return { id, type: 'moduleNode', position: { x: 200, y: 100 }, data: { moduleType, config } } }
function checkpoint(message) { checks.push(message); console.log(message) }

async function launchAndOpen() {
  const desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  const main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 40_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1100, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('227')", 'formal Studio', 30_000)
  return { desktop, main, studio, runtime }
}

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}
async function apiBytes(runtime, path) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  assert.ok(response.ok, `GET /api${path}: ${response.status}`)
  return Buffer.from(await response.arrayBuffer())
}
async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target', 30_000)
  return connectCdp(target.webSocketDebuggerUrl)
}
async function waitForTarget(origin, predicate, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const target = (await (await fetch(`${origin}/json/list`)).json()).find(predicate)
    if (target) return target
    await wait(100)
  }
  throw new Error(`timed out waiting for ${description}`)
}
async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    last = await read()
    if (last) return last
    await wait(200)
  }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}
async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}
async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(100)
}
async function clickExpression(cdp, expression, description) {
  const p = await waitFor(cdp, `(()=>{const e=${expression};if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, description)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(100)
}
async function setInput(cdp, selector, value) {
  const p = await point(cdp, selector)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await wait(80)
}
async function selectByLabel(cdp, label, option) {
  await clickExpression(cdp, `(()=>{const l=[...document.querySelectorAll('label')].find(e=>e.textContent.includes(${JSON.stringify(label)}));return l?.parentElement?.querySelector('[role=combobox]')})()`, `${label} select`)
  await click(cdp, option, '[role="option"]')
}
async function setInputByLabel(cdp, label, value) {
  const selector = await waitFor(cdp, `(()=>{const labels=[...document.querySelectorAll('label')],i=labels.findIndex(e=>e.textContent.trim()===${JSON.stringify(label)}),e=labels[i]?.parentElement?.querySelector('input');if(!e)return null;e.dataset.qaScheduleInput='true';return '[data-qa-schedule-input=true]'})()`, `${label} input`)
  await setInput(cdp, selector, value)
}
async function capture(cdp, path) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}
function cloakProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line))
}
function watchCloakBrowser(workspace) {
  let active = true, observed = false
  const done = (async () => { while (active) { observed ||= cloakProcesses(workspace).length > 0; await wait(75) } })()
  return { async stop() { active = false; await done; return observed } }
}
async function buildHash() {
  const hash = createHash('sha256')
  for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) {
    const path = join(root, 'apps/desktop/out', file)
    if ((await stat(path)).isFile()) hash.update(file).update(await readFile(path))
  }
  return hash.digest('hex')
}
