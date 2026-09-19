import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { mkdir, mkdtemp, readFile, readdir, realpath, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { promisify } from 'node:util'
import { createInterface } from 'node:readline/promises'
import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..'), exec = promisify(execFile)
const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm3-management-')))
const workspace = join(owner, 'workspace')
await mkdir(workspace)
await writeFile(join(owner, '.pm3-management-qa.json'), JSON.stringify({ kind: 'pm3-management-qa', createdAt: new Date().toISOString() }))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))
const directory = join(root, 'docs/project-management/implementation/pm3/management-runs')
await mkdir(directory, { recursive: true })
const evidence = await mkdtemp(join(directory, 'run-')), checks = [], screenshots = []
let desktop, renderer, native, runtime
const rendererDir = join(root, 'apps/desktop/out/renderer/assets')
const bundles = (await readdir(rendererDir)).filter(name => /\.(js|css)$/.test(name)).sort()
const buildSha256 = createHash('sha256'); for (const name of bundles) buildSha256.update(name).update(await readFile(join(rendererDir, name)))
const buildHash = buildSha256.digest('hex')
const sourceDigest = createHash('sha256')
for (const sourceRoot of ['apps/desktop/src', 'apps/backend/src']) {
  for (const name of (await readdir(join(root, sourceRoot), { recursive: true })).filter(name => /\.(tsx?|css|py)$/.test(name)).sort()) sourceDigest.update(`${sourceRoot}/${name}`).update(await readFile(join(root, sourceRoot, name)))
}
const sourceHash = sourceDigest.digest('hex')
const head = (await exec('git', ['rev-parse', 'HEAD'], { cwd: root })).stdout.trim()
const check = (id, result) => { checks.push({ id, result, type: 'real-electron-http-sqlite' }); console.log(`${id}: ${result}`) }
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.pm3Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm3Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
  await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(renderer, "document.body.innerText.includes('本地服务正常')", 'local backend ready', 30000)
  runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  assert.ok(runtime.workspaceKey.startsWith(owner), 'Only the tool-owned workspace may be changed')
}
async function close() { renderer?.close(); native?.close(); await stop(desktop?.child); desktop = renderer = native = undefined }
async function click(text, selector = 'button') {
  const point = await waitFor(renderer, `(()=>{const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled&&((()=>{const c=e.cloneNode(true);c.querySelectorAll('[aria-hidden="true"]').forEach(n=>n.remove());return c.textContent.trim()})()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}||e.labels?.[0]?.textContent.trim()===${JSON.stringify(text)}));if(items.length!==1)return null;const e=items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `control ${text}`)
  for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
  await wait(100)
}
async function input(selector, value) {
  await waitFor(renderer, `!!document.querySelector(${JSON.stringify(selector)})`, selector)
  // Focus and send real keyboard input. No React state or business callbacks are invoked.
  await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.focus();e.select();return true})()`)
  await renderer.command('Input.insertText', { text: value }); await wait(120)
}
async function api(path, { method = 'GET', body } = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, { method, headers: { 'Content-Type': 'application/json', 'x-autoflow-token': runtime.sidecar.token, 'Idempotency-Key': randomUUID() }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const text = await response.text(); assert.ok(response.ok, `${path}: ${response.status} ${text}`); return JSON.parse(text)
}

async function dropSaveResponseAndFirstLookup() {
  let droppedSave = false, droppedLookup = false, originalKey
  const listener = async event => {
    const message = JSON.parse(event.data)
    if (message.method !== 'Fetch.requestPaused') return
    const { requestId, request, responseStatusCode } = message.params
    const dropSave = !droppedSave && request.method === 'PUT' && responseStatusCode === 200
    const dropLookup = droppedSave && !droppedLookup && request.url.includes('/operations/by-idempotency-key/')
    if (dropSave || dropLookup) {
      if (dropSave) { droppedSave = true; originalKey = Object.entries(request.headers).find(([key]) => key.toLowerCase() === 'idempotency-key')?.[1] }
      else droppedLookup = true
      await renderer.command('Fetch.failRequest', { requestId, errorReason: 'ConnectionReset' })
    } else await renderer.command('Fetch.continueRequest', { requestId })
  }
  renderer.socket.addEventListener('message', listener)
  await renderer.command('Fetch.enable', { patterns: [{ urlPattern: '*api/v1/projects/*', requestStage: 'Response' }] })
  return async () => {
    await renderer.command('Fetch.disable'); renderer.socket.removeEventListener('message', listener)
    assert.ok(droppedSave && droppedLookup && originalKey, 'Injected failure must occur after successful real save and during original lookup')
    return originalKey
  }
}

async function capture(id, reference) {
  await waitFor(renderer, `!document.querySelector('[aria-label="关闭通知"]')`, 'notifications finish', 5000)
  await renderer.evaluate('window.scrollTo(0,0);true'); await wait(180)
  const metadata = await renderer.evaluate('({viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,font:getComputedStyle(document.body).fontFamily,documentWidth:document.documentElement.scrollWidth})')
  const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(evidence, `${id}.png`), Buffer.from(data, 'base64'))
  const nativeWindow = await native.evaluate('(()=>{const w=pm3Electron.BrowserWindow.getAllWindows()[0];return {contentBounds:w.getContentBounds(),zoomFactor:w.webContents.getZoomFactor()}})()')
  screenshots.push({ id, buildHash, sourceHash, nativeWindow, file: `${id}.png`, reference, ...metadata, visualReview: 'pending' })
}
try {
  await launch()
  const workflowId = randomUUID()
  await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', `from pathlib import Path
from uuid import uuid4
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.application.workflows.service import WorkflowService
from tests.fixtures.workflows import workflow_payload
import sys
factory=create_session_factory(AppPaths.from_data_dir(Path(sys.argv[1])).database)
document=workflow_payload(sys.argv[2]); document['content']['name']='资料整理流程'
WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(document,str(uuid4()))
factory.dispose()`, runtime.workspaceKey, workflowId], { cwd: root })
  check('PM3-M00', '工作流资料通过真实文档服务预置；未操作 Studio，未制造运行结果')
  await click('项目'); await click('新建项目'); await input('#project-name', '自动化管理验收'); await input('#project-description', '整理资料与维护自动化配置'); await click('创建项目')
  await waitForProjectPage(renderer)
  const project = (await api('/projects?q=自动化管理验收')).items[0]
  await click('数据', '[aria-label=项目功能] button'); await click('新建数据表')
  await input('#data-table-name', '内容资料库'); await input('#data-table-description', '自动化输入管理验收'); await click('创建数据表')
  await click('字段与校验', '[role=tab]'); await click('新增字段'); await input('#field-name', '标题'); await input('#field-key', 'title'); await click('应用到草稿')
  await click('保存字段'); await click('确认保存字段')
  await waitFor(renderer, "document.body.innerText.includes('暂无未保存修改')", 'real field saved')
  const table = (await api(`/projects/${project.projectId}/tables`)).items[0]
  const field = (await api(`/projects/${project.projectId}/tables/${table.tableId}/fields`)).items[0]
  check('PM3-M06', 'UI 创建真实数据表与字段，作为自动化输入选择的资料；不执行数据任务')
  await click('自动化', '[aria-label=项目功能] button')
  await capture('01-empty', '/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13/latest/02-automation/006-automation-empty-695f71.png')
  await click('新建自动化')
  await input('[aria-label="自动化名称"]', '资料整理')
  await input('[aria-label="用途说明"]', '将采集内容整理为可维护的资料记录')
  await click('关联工作流', '[role=combobox]'); await click('资料整理流程', '[role=option]')
  await click('输入与参数', '[role=tab]'); await click('新增参数')
  await input('[aria-label="参数名称 " ]', '关键词')
  await input('[aria-label="参数说明 关键词"]', '用于筛选资料')
  await capture('02-inputs', 'docs/prototype/project-management-pm3/automation-detail-inputs.png')
  await click('添加数据输入'); await input('[aria-label="输入别名 "]', '资料')
  await click('添加字段映射 资料')
  await click('添加排序')
  await click('保存配置')
  await waitFor(renderer, "document.body.innerText.includes('筛选或排序有尚未应用的修改')", 'unapplied input prevents global save')
  assert.equal((await api(`/projects/${project.projectId}/automations`)).total, 0)
  await click('应用筛选')
  await click('运行设置', '[role=tab]'); await input('[aria-label="最大任务数"]', '3')
  await input('[aria-label="单任务超时（分钟）"]', '0.5')
  await capture('03-run-settings', 'docs/prototype/project-management-pm3/automation-detail-run-policy.png')
  await click('保存配置')
  await waitFor(renderer, "document.body.innerText.includes('自动化已创建')", 'automation created')
  let automation = (await api(`/projects/${project.projectId}/automations`)).items[0]
  assert.equal(automation.parameterSchema[0].name, '关键词'); assert.equal(automation.parameterSchema[0].description, '用于筛选资料'); assert.equal(automation.runPolicy.maxTasks, 3); assert.equal(automation.runPolicy.automaticExecutionTimeoutSeconds, 30)
  assert.equal(Object.hasOwn(automation.parameterSchema[0], 'defaultValue'), false)
  assert.equal(automation.inputPlan.inputs[0].orderBy[0].fieldId, field.ref.fieldId)
  assert.equal(automation.inputPlan.inputs[0].fieldBindings[0].fieldRef.fieldId, field.ref.fieldId)
  check('PM3-M07', '输入筛选草稿先应用再整体保存；真实字段绑定与排序被 HTTP 接受并持久保存')
  check('PM3-M01', 'UI 创建项目与自动化，跨页签参数/运行配置一次保存，后端保留未提供默认值与秒数')
  await capture('04-overview', 'docs/prototype/project-management-pm3/automation-detail-overview.png')
  await click('资源与环境', '[role=tab]'); await click('不使用代理', 'input[type=radio]')
  await click('模型提供方', '[role=combobox]'); await click('不指定模型提供方', '[role=option]')
  await capture('05-resources', 'docs/prototype/project-management-pm3/automation-detail-resources.png')
  await click('保存配置'); await waitFor(renderer, "document.body.innerText.includes('自动化配置已保存')", 'resource saved')
  automation = await api(`/projects/${project.projectId}/automations/${automation.automationId}`)
  assert.deepEqual(automation.environmentPolicy.proxyOverride, { mode: 'none' }); assert.equal(automation.environmentPolicy.modelProviderId, null)
  await click('基本信息', '[role=tab]'); await input('[aria-label="用途说明"]', '我的未保存修改')
  const draftUrl = await renderer.evaluate('location.hash')
  await click('返回自动化目录')
  await waitFor(renderer, "document.body.innerText.includes('放弃未保存的修改？')", 'dirty leave guard')
  await capture('10-leave-draft', 'docs/prototype/project-management-pm3/automation-detail-overview.png#leave')
  await renderer.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await waitFor(renderer, "!document.querySelector('[role=alertdialog]')", 'escape keeps draft')
  assert.equal(await renderer.evaluate('location.hash'), draftUrl)
  assert.equal(await renderer.evaluate("document.querySelector('[aria-label=用途说明]').value"), '我的未保存修改')
  check('PM3-M05', '真实导航离开保护：Escape 取消离开，URL 与未保存输入保持一致')
  const { automationId, projectId, managementRevision, capabilityRequirements, createdAt, updatedAt, ...write } = automation
  await api(`/projects/${projectId}/automations/${automationId}`, { method: 'PUT', body: { ...write, description: '另一个窗口的修改', expectedManagementRevision: managementRevision } })
  await click('保存配置'); await waitFor(renderer, "document.body.innerText.includes('你的输入已保留')", 'real CAS conflict')
  assert.equal(await renderer.evaluate("document.querySelector('[aria-label=用途说明]').value"), '我的未保存修改')
  await capture('06-conflict', 'docs/prototype/project-management-pm3/automation-detail-overview.png#conflict')
  check('PM3-M02', '真实竞争编辑产生 CAS 冲突，管理页保留用户输入')
  await click('载入最新资料重新编辑'); await click('载入最新资料')
  assert.equal(await renderer.evaluate("document.querySelector('[aria-label=用途说明]').value"), '另一个窗口的修改')
  await input('[aria-label="用途说明"]', '响应丢失后恢复的修改')
  const stopInjection = await dropSaveResponseAndFirstLookup()
  await click('保存配置')
  await waitFor(renderer, "document.body.innerText.includes('保存结果尚未确认')", 'unknown save result')
  const originalKey = await stopInjection()
  await capture('08-unknown-result', 'docs/prototype/project-management-pm3/automation-detail-overview.png#unknown')
  await click('核对保存结果')
  await waitFor(renderer, "!document.body.innerText.includes('保存结果尚未确认') && document.body.innerText.includes('配置已保存')", 'recovered original operation')
  const original = await api(`/projects/${projectId}/operations/by-idempotency-key/${originalKey}`)
  const afterUnknown = await api(`/projects/${projectId}/automations/${automationId}`)
  assert.equal(original.result.managementRevision, afterUnknown.managementRevision)
  assert.equal(afterUnknown.managementRevision, managementRevision + 2)
  assert.equal(afterUnknown.description, '响应丢失后恢复的修改')
  check('PM3-M04', '测试注入：真实 PUT 提交后丢失响应与首次查询；UI 原键核验恢复，不重复写入')
  await native.evaluate('pm3Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2);true')
  await capture('09-overview-200-percent', 'docs/prototype/project-management-pm3/automation-detail-overview.png#200-percent')
  assert.ok(await renderer.evaluate('document.documentElement.scrollWidth <= innerWidth'), '200% zoom must not widen the application')
  await native.evaluate('pm3Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1);true')
  await click('返回自动化目录')
  await capture('07-directory', '/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13/latest/02-automation/001-automation-v1-approved-a45201.png')
  const directoryReads = []
  const observeReads = event => { const message = JSON.parse(event.data); if (message.method === 'Network.requestWillBeSent' && message.params.request.url.includes(`/projects/${projectId}/automations?`)) directoryReads.push(message.params.request.url) }
  await renderer.command('Network.enable'); renderer.socket.addEventListener('message', observeReads)
  await input('[aria-label="搜索自动化"]', '没有这个自动化')
  await wait(350)
  assert.equal(directoryReads.length, 0, 'Typing a search draft must not query the backend')
  assert.equal(await renderer.evaluate("document.querySelectorAll('[data-testid=automation-grid] article').length"), 1)
  await renderer.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r' })
  await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await waitFor(renderer, "document.body.innerText.includes('没有找到匹配的自动化')", 'submitted search reaches real backend')
  assert.equal(directoryReads.length, 1)
  await capture('11-no-match', '/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13/latest/02-automation/007-no-results-8f42cb.png')
  await click('清除搜索条件')
  await waitFor(renderer, "document.querySelectorAll('[data-testid=automation-grid] article').length===1", 'clear search restores directory')
  await input('[aria-label="搜索自动化"]', '资料')
  await click('应用自动化搜索')
  await waitFor(renderer, "document.querySelectorAll('[data-testid=automation-grid] article').length===1 && !document.querySelector('input[aria-busy=true]')", 'button applies search')
  renderer.socket.removeEventListener('message', observeReads)
  check('PM3-M08', '目录输入期间不查询；Enter与搜索按钮应用真实查询，无匹配与清除正确恢复')
  await close(); await launch(); await click('项目')
  const persisted = await api(`/projects/${project.projectId}/automations/${automation.automationId}`)
  assert.equal(persisted.description, '响应丢失后恢复的修改'); assert.equal(persisted.runPolicy.maxTasks, 3)
  check('PM3-M03', '真实 Electron/服务重启后管理配置事实仍持久存在（重启后的事实核对使用 GET）')
  await writeFile(join(evidence, 'result.json'), JSON.stringify({ status: 'passed', head, sourceHash, buildHash, platform: process.platform, arch: process.arch, workspace: owner, checkedAt: new Date().toISOString(), checks, screenshots, scriptSha256: createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'), notExecuted: ['Studio', 'Windows', 'packaged app', 'user manual acceptance'], visualReview: 'pending' }, null, 2))
  if (process.argv.includes('--manual')) {
    console.log('管理验收应用已保持打开。可测试自动化管理验收项目；输入 s 保存截图，q 退出。')
    const cli = createInterface({ input: process.stdin, output: process.stdout })
    try { for await (const answer of cli) { if (answer.trim() === 'q') break; if (answer.trim() === 's') { await capture(`manual-${Date.now()}`, 'user-manual'); console.log(`截图：${evidence}`) } } } finally { cli.close() }
  }
} catch (error) {
  try { if (renderer) await capture('failure', 'unassigned') } catch { /* Keep the original failure. */ }
  await writeFile(join(evidence, 'result.json'), JSON.stringify({ status: 'failed', head, workspace: owner, checks, screenshots, error: String(error), visualReview: 'pending' }, null, 2))
  throw error
} finally { await close(); console.log(`Evidence: ${evidence}\nIsolated workspace retained: ${owner}`) }
