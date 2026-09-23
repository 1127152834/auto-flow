import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { connectCdp, launchElectron, waitFor, waitForProjectPage } from './electron-cdp.mjs'
import { checkProjectManagement, installRuntimeKernel, projectSmokeOptions } from './smoke-project-management.mjs'
import { checkProjectRuntime } from './project-runtime-smoke.mjs'
import { checkProjectVolume } from './project-volume-smoke.mjs'
import { assertOutsideHistory, redactSidecarLog } from './project-smoke-output.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const options = projectSmokeOptions(process.argv.slice(2))
if (options['output-dir']) await assertOutsideHistory(join(root, 'docs/migration/project-management-pm1-qa'), options['output-dir'])
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm9 desktop 中文-')))
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(userData, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: userData, previousPath: null, preferences: { zoom: 100, motion: 'reduce' } }))
let desktop
let sidecar
let cdp
let native
let studio
let report = { status: 'failed', platform: process.platform, arch: process.arch, packaged: Boolean(options.executable), startedAt: new Date().toISOString(), checks: [], screenshots: [] }
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'], cliArgs: options.executable ? ['--executable', options.executable] : [] })
  cdp = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.pm9Electron = process.getBuiltinModule('module').createRequire(process.cwd() + '/package.json')('electron'); true")
  await cdp.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  return waitFor(cdp, `(async()=>{const r=await window.autoflow.getRuntimeContext(); return r.sidecar.state==='ready'?r.sidecar:null})()`, 'production sidecar ready', 60_000)
}
async function click(text, selector = 'button', target = cdp) {
  const point = await waitFor(target, `(()=>{const elements=[...document.querySelectorAll(${JSON.stringify(selector)})];const e=elements.find(e=>e.getClientRects().length&&!e.disabled&&(!${JSON.stringify(text)}||e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}));if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `button ${text}`)
  for (const type of ['mousePressed', 'mouseReleased']) await target.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
}
async function fill(selector, value, target = cdp) {
  await waitFor(target, `Boolean(document.querySelector(${JSON.stringify(selector)}))`, selector)
  await target.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select()})()`)
  await target.command('Input.insertText', { text: value })
}
async function capture(name, target = cdp) {
  if (!options['output-dir']) return
  await mkdir(options['output-dir'], { recursive: true })
  const { data } = await target.command('Page.captureScreenshot', { format: 'png' })
  const filename = `project-${name}.png`
  await writeFile(join(options['output-dir'], filename), data, 'base64')
  report.screenshots.push(filename)
}
async function api(path, body, method = body === undefined ? 'GET' : 'POST', expectedStatus, key = randomUUID()) {
  const response = await fetch(sidecar.baseUrl + path, { method, headers: { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': key }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(30_000) })
  const value = await response.json()
  assert.ok(expectedStatus === undefined ? response.ok : response.status === expectedStatus, `${method} ${path}: ${response.status} ${JSON.stringify(value)}`)
  return value
}
async function poll(check, label) {
  for (let attempt = 0; attempt < 300; attempt++) {
    const value = await check()
    if (value) return value
    await new Promise(resolvePoll => setTimeout(resolvePoll, 200))
  }
  throw new Error(`Timeout: ${label}`)
}
async function checkAutomationDeletion(browserVersion) {
  const project = await api('/api/v1/projects', { name: '独立流程解除关联验收' })
  const prefix = `/api/v1/projects/${project.projectId}`
  const profile = await api('/api/v1/profiles', { name: '解除关联真实浏览器', browserVersion, headless: true })
  const nodes = [
    { id: 'open', type: 'open_page', position: { x: 0, y: 0 }, data: { moduleType: 'open_page', url: 'about:blank' } },
    { id: 'manual', type: 'project_manual', position: { x: 0, y: 100 }, data: { moduleType: 'project_manual', reason: '验证占用删除保护', timeoutSeconds: 300 } },
    { id: 'end', type: 'project_end', position: { x: 0, y: 200 }, data: { moduleType: 'project_end', retainEnvironment: { enabled: false } } },
  ]
  const workflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: '删除自动化后保留独立文档', variables: [], nodes, edges: [{ id: 'open-manual', source: 'open', target: 'manual' }, { id: 'manual-end', source: 'manual', target: 'end' }] })
  const body = { name: '解除关联测试自动化', description: '', workflowId: workflow.id, inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }, runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 120, manualDeadlineSeconds: 300 } }
  const automation = await api(prefix + '/automations', body)
  const automationPath = prefix + `/automations/${automation.automationId}`
  const duplicate = await api(prefix + '/automations', { ...body, name: '不得重复关联' }, 'POST', 409)
  assert.equal(duplicate.error.code, 'WORKFLOW_ALREADY_BOUND')
  const accepted = await api(automationPath + '/batches', { expectedAutomationRevision: automation.managementRevision, parameters: {}, maxTasks: 1, concurrency: 1 })
  const batchId = accepted.operation.result.batch.batchId
  const manual = await poll(async () => (await api(prefix + '/manual-items')).items.find(item => item.status === 'waiting'), 'real worker waiting before automation deletion')
  const taskBefore = await api(prefix + `/tasks/${manual.taskId}`)
  assert.equal(taskBefore.run.status, 'waiting_manual')
  const documentBefore = await api(`/api/workflows/${workflow.id}`)
  async function preparedCount() {
    const python = join(root, 'apps/backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    const { stdout } = await promisify(execFile)(python, ['-c', "import sqlite3,sys; from pathlib import Path; db=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True); print(db.execute('SELECT count(*) FROM project_workflow_prepared_contents WHERE workflow_id=?',(sys.argv[2],)).fetchone()[0]); db.close()", join(userData, 'data/autoflow.sqlite3'), workflow.id], { timeout: 10_000 })
    return Number(stdout.trim())
  }
  assert.equal(await preparedCount(), 1)
  const deletes = []
  const observe = event => {
    const message = JSON.parse(event.data)
    const request = message.method === 'Network.requestWillBeSent' && message.params.request
    if (request && request.method === 'DELETE' && request.url === sidecar.baseUrl + automationPath) deletes.push(request)
  }
  await cdp.command('Network.enable')
  cdp.socket.addEventListener('message', observe)
  try {
    await cdp.evaluate(`location.hash=${JSON.stringify('#/projects/' + project.projectId + '/automations/' + automation.automationId)}`)
    await click('删除自动化', '[aria-label="危险操作"] button')
    await waitFor(cdp, "document.querySelector('[aria-label=阻断项]')?.innerText.includes('批次尚未结束')", 'live batch deletion blocker')
    assert.ok(await cdp.evaluate("document.querySelector('[aria-label=将保留]').innerText.includes('工作流文档保留，只解除关联')"))
    assert.ok(await cdp.evaluate("document.querySelector('[aria-label=将删除]').innerText.includes('运行方案 1 个及其任务与事件')"))
    await capture('automation-delete-busy')
    await fill('[aria-label="确认自动化名称"]', body.name)
    await click('删除自动化', '[role=dialog] button')
    await waitFor(cdp, "[...document.querySelectorAll('[role=dialog] [role=alert]')].some(e=>e.innerText==='操作失败，请重试')", 'busy delete rejected in UI')
    assert.equal((await api(automationPath)).automationId, automation.automationId)
    assert.equal((await api(prefix + `/tasks/${manual.taskId}`)).run.status, 'waiting_manual')
    const batch = await api(prefix + `/batches/${batchId}`)
    await api(prefix + `/batches/${batchId}/stop`, { expectedStatusRevision: batch.batch.statusRevision, reason: '完成解除关联前先停止真实任务' })
    await poll(async () => (await api(prefix + `/batches/${batchId}`)).batch.status === 'stopped', 'stopped worker releases automation')
    await click('删除自动化', '[role=dialog] button')
    await waitFor(cdp, "document.body.innerText.includes('影响范围可能已变化，请重新核对后再确认。')", 'old impact rejected after worker stop')
    assert.equal(await cdp.evaluate("document.querySelector('[aria-label=确认自动化名称]').value"), '')
    await capture('automation-delete-stale')
    await click('重新核对影响')
    await waitFor(cdp, "document.querySelector('[aria-label=阻断项]')?.innerText.includes('没有阻断项')", 'fresh delete impact after worker cleanup')
    await fill('[aria-label="确认自动化名称"]', '错误名称')
    assert.equal(await cdp.evaluate("[...document.querySelectorAll('[role=dialog] button')].find(e=>e.textContent.trim()==='删除自动化').disabled"), true)
    await fill('[aria-label="确认自动化名称"]', body.name)
    await capture('automation-delete-ready')
    await click('删除自动化', '[role=dialog] button')
    await waitFor(cdp, `location.hash===${JSON.stringify('#/projects/' + project.projectId + '/automations')} && !document.querySelector('[role=dialog]')`, 'automation deleted through UI')
    await api(automationPath, undefined, 'GET', 404)
    await api(prefix + `/batches/${batchId}`, undefined, 'GET', 404)
    await api(prefix + `/tasks/${manual.taskId}`, undefined, 'GET', 404)
    assert.equal(await preparedCount(), 0, 'owned frozen snapshot must be removed before its batch lookup disappears')
    assert.equal((await api(prefix + '/manual-items')).items.filter(item => item.taskId === manual.taskId).length, 0, 'terminal manual items must not point at deleted tasks')
    const documentAfter = await api(`/api/workflows/${workflow.id}`)
    for (const key of ['id', 'revision', 'nodes', 'edges']) assert.deepEqual(documentAfter[key], documentBefore[key], `independent workflow ${key} must survive`)
    assert.equal(deletes.length, 3, 'UI issues one command for each explicit busy/stale/fresh confirmation')
    const request = deletes.at(-1)
    const key = Object.entries(request.headers).find(([name]) => name.toLowerCase() === 'idempotency-key')?.[1]
    assert.ok(key)
    const operation = await api(prefix + `/operations/by-idempotency-key/${key}`)
    const replay = await api(automationPath, JSON.parse(request.postData), 'DELETE', 200, key)
    assert.equal(replay.operation.operationId, operation.operationId)
    assert.equal(replay.operation.status, 'succeeded')
    const linkedAgain = await api(prefix + '/automations', { ...body, name: '重新关联保留的独立文档' })
    assert.equal(linkedAgain.workflowId, workflow.id)
    await capture('automation-unlinked')
    return { status: 'passed', projectId: project.projectId, workflowId: workflow.id, removedAutomationId: automation.automationId, operationId: operation.operationId, checks: ['one independent workflow cannot be associated twice', 'real waiting worker blocks deletion without losing its task or document', 'stop invalidates old UI impact and clears name confirmation', 'fresh exact-name UI deletion removes automation/batch/task, terminal manual item and frozen snapshot while keeping the original document', 'replaying the accepted original delete key returns the same operation', 'retained independent document can be associated again'], limits: ['project-owned document deletion remains refused because ownership is not persisted', 'Studio editing ownership and Windows/Intel physical UI acceptance are not proved'] }
  } finally { cdp.socket.removeEventListener('message', observe) }
}

async function checkStandaloneStudio(browserVersion) {
  assert.equal((await api('/api/v1/projects')).total, 0)
  const profile = await api('/api/v1/profiles', { name: '独立 Studio 配置', browserVersion, browserEdition: 'public', headless: true })
  const standalone = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: '零项目通用网页', variables: [], nodes: [
    { id: 'open-general', type: 'open_page', position: { x: 100, y: 100 }, data: { moduleType: 'open_page', label: '通用网页', url: 'about:blank' } },
  ], edges: [] })
  const tableId = randomUUID(), datasetGeneration = randomUUID(), fieldId = randomUUID()
  const projectData = { moduleType: 'project_data', label: '项目写回', operation: 'createRecord', variableName: 'saved_record',
    tableGrant: { tableId, datasetGeneration, fieldIds: [fieldId], operations: ['createRecord'], readPurposes: [] },
    arguments: { tableId, datasetGeneration, values: { [fieldId]: '必须保留的配置' } } }
  const document = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: '缺项目能力仍可编辑', variables: [], nodes: [
    { id: 'write-project', type: 'project_data', position: { x: 100, y: 100 }, data: projectData },
  ], edges: [] })
  await click('工作流工作台编排并运行浏览器自动化流程')
  const studioTarget = await poll(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(target => target.type === 'page' && target.url.includes('view=automation-studio')), 'standalone Studio window')
  studio = await connectCdp(studioTarget.webSocketDebuggerUrl)
  try {
    await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await waitFor(studio, "document.body.innerText.includes('模块库')", 'production Studio ready', 30_000)
    assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
    await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value===${JSON.stringify(profile.id)}`, 'independent browser profile')
    await click('打开', 'button', studio)
    await click('打开工作流 ' + standalone.name, '[role=button]', studio)
    await waitFor(studio, "Boolean(document.querySelector('.react-flow__node[data-id=\"open-general\"]'))", 'standalone workflow loaded')
    await click('运行 (F5)', '[aria-label="运行 (F5)"]', studio)
    await click('无头运行', '[role=menuitem]', studio)
    const run = await poll(async () => {
      const page = await api(`/api/workflow-runs?documentId=${standalone.id}&cursor=0&limit=20`)
      const value = page.items[0]
      if (!value) return null
      const current = await api(`/api/workflow-runs/${value.runId}`)
      return ['completed', 'failed', 'stopped', 'interrupted'].includes(current.status) ? current : null
    }, 'independent real browser run')
    assert.equal(run.status, 'completed')
    await waitFor(studio, "document.body.innerText.includes('执行完成')", 'Studio terminal event')
    assert.equal((await api('/api/v1/projects')).total, 0)
    await capture('studio-independent-run', studio)
    await click('打开', 'button', studio)
    await click('打开工作流 ' + document.name, '[role=button]', studio)
    await waitFor(studio, "Boolean(document.querySelector('.react-flow__node[data-id=\"write-project\"]'))", 'project write document loaded')
    await click('', '.react-flow__node[data-id="write-project"]', studio)
    await waitFor(studio, "document.body.innerText.includes('从项目自动化批次运行。使用任务的输入快照和数据权限')", 'explicit project capability guidance')
    await capture('studio-project-context', studio)
    await click('运行 (F5)', '[aria-label="运行 (F5)"]', studio)
    await click('无头运行', '[role=menuitem]', studio)
    const refusal = await waitFor(studio, "[...document.querySelectorAll('[role=alert]')].find(e=>e.innerText.includes('执行失败:'))?.innerText", 'standalone project node admission refused')
    assert.ok(refusal.includes('HTTP 422') && refusal.includes('工作流包含尚未迁入或无法运行的节点'))
    assert.equal((await api(`/api/workflow-runs?documentId=${document.id}&cursor=0&limit=20`)).items.length, 0)
    const afterRefusal = await api(`/api/workflows/${document.id}`)
    assert.equal(afterRefusal.revision, document.revision)
    assert.deepEqual(afterRefusal.nodes, document.nodes)
    await capture('studio-capability-refused', studio)
    await fill('#project-data-result', 'edited_record', studio)
    await click('保存', 'button', studio)
    await waitFor(studio, `document.body.innerText.includes(${JSON.stringify('工作流已保存: ' + document.name)})`, 'project document saved from Studio')
    const edited = await api(`/api/workflows/${document.id}`)
    assert.ok(edited.revision > document.revision)
    const node = edited.nodes.find(node => node.id === 'write-project')
    assert.ok(node)
    assert.equal(node.data.variableName, 'edited_record')
    for (const key of ['moduleType', 'operation', 'tableGrant', 'arguments']) assert.deepEqual(node.data[key], projectData[key], `Studio retains project ${key}`)
    assert.equal((await api('/api/v1/projects')).total, 0)
    assert.equal((await api('/api/workflow-runs?cursor=0&limit=20')).items.length, 1)
    await capture('studio-project-document-saved', studio)
    return { status: 'passed', standaloneWorkflowId: standalone.id, projectWorkflowId: document.id, runId: run.runId, refusal, checks: ['zero Project before and after independent real browser run', 'actual Studio displays project context guidance; existing standalone admission returns HTTP 422 unsupported node, creates no run and leaves the document unchanged', 'actual Studio edit/save retains project node identity, operation, arguments and frozen grant without implicit Project'], limits: [`one ${process.platform}/${process.arch} application window; full Studio module/physical platform gates remain separate`] }
  } catch (error) {
    await capture('studio-failure', studio).catch(() => {})
    throw error
  } finally {
    studio.close()
    await native.evaluate("pm9Electron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('view=automation-studio'))?.close()")
    studio = undefined
  }
}
try {
  const browserVersion = options['runtime-kernel'] ? await installRuntimeKernel(options['runtime-kernel'], userData) : null
  sidecar = await launch()
  if (browserVersion) report.standaloneStudio = await checkStandaloneStudio(browserVersion)
  await click('项目')
  await click('新建项目')
  await waitFor(cdp, "document.activeElement?.id==='project-name'", 'keyboard autofocus')
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  assert.equal(await cdp.evaluate('document.activeElement.id'), 'project-description')
  await fill('#project-name', 'PM9 桌面项目')
  await fill('#project-description', '真实界面创建与中文空格路径')
  await click('创建项目')
  await waitForProjectPage(cdp)
  const response = await fetch(`${sidecar.baseUrl}/api/v1/projects`, { headers: { 'x-autoflow-token': sidecar.token } })
  assert.equal(response.status, 200)
  const project = (await response.json()).items.find(item => item.name === 'PM9 桌面项目')
  assert.ok(project)
  report = { ...report, ...await checkProjectManagement(sidecar.baseUrl, sidecar.token, project) }
  report.checks.push('Electron UI creates project with keyboard focus and real preload/sidecar authentication')
  await cdp.command('Page.reload', { ignoreCache: true })
  await waitForProjectPage(cdp)
  const pages = [
    ['概览', '今日数据变化'], ['自动化', '还没有自动化'], ['运行记录', '还没有运行记录'],
    ['统计', '按日处理量'], ['数据', '中文 数据表'], ['环境', '当前没有临时现场'],
  ]
  for (const [tab, expected] of pages) {
    await click(tab, '[aria-label="项目功能"] button')
    await waitFor(cdp, `document.querySelector('[aria-label="项目功能"] [aria-current=page]')?.textContent.trim()===${JSON.stringify(tab)} && document.body.innerText.includes(${JSON.stringify(expected)})`, `live ${tab} page`)
    await waitFor(cdp, "!document.querySelector('main [role=progressbar]')", 'page settled')
    assert.equal(await cdp.evaluate("document.body.innerText.includes('暂未开放')"), false)
    await capture(tab)
  }
  report.checks.push('all six project tabs open settled production pages')
  if (browserVersion) {
    report.automationDeletion = await checkAutomationDeletion(browserVersion)
    report.runtime = await checkProjectRuntime(sidecar.baseUrl, sidecar.token, browserVersion, { resumeManual: async (projectId, item) => {
      await cdp.evaluate(`location.hash=${JSON.stringify('#/projects/' + projectId + '/runs/manual/' + item.manualItemId)}`)
      await waitFor(cdp, "Boolean(document.querySelector('input[type=radio][value=continue]:not(:disabled)'))", 'live manual continuation ready')
      await cdp.evaluate("document.querySelector('input[type=radio][value=continue]').click()")
      await fill('[aria-label="确认码"]', 'verified')
      await capture('manual-declared-input')
      await click('提交处理结果')
      await waitFor(cdp, "!document.querySelector('[aria-label=确认码]')", 'manual command accepted and directory restored')
      report.checks.push('manual detail submits declared input to the same real worker and selects one direct successor')
    } })
    report.volume = await checkProjectVolume(sidecar, cdp, click, report.runtime, userData)
    report.boundary = 'production management, real runtime and renderer volume; live Sheets and physical installation remain pending'
    await capture('volume')
    await cdp.evaluate(`location.hash=${JSON.stringify('#/projects/' + project.projectId + '/environments')}`)
    await waitFor(cdp, "document.querySelector('[aria-label=\"项目功能\"] [aria-current=page]')?.textContent.trim()==='环境' && !document.querySelector('main [role=progressbar]')", 'environment route settled before zoom')
  }
  await native.evaluate('pm9Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2)')
  await waitFor(native, 'pm9Electron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()===2', 'native 200% zoom applied', 5_000)
  await waitFor(cdp, 'document.documentElement.scrollWidth <= innerWidth + 1', '200% zoom has no document horizontal overflow')
  await capture('zoom-200')
  await native.evaluate('pm9Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1)')
  await waitFor(native, 'pm9Electron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()===1', 'native zoom reset', 5_000)
  await cdp.evaluate('window.autoflow.openAutomationStudio()')
  let studioTarget
  for (let attempt = 0; attempt < 100; attempt++) {
    const targets = await (await fetch(`${desktop.debugOrigin}/json/list`)).json()
    studioTarget = targets.find(target => target.type === 'page' && target.url.includes('view=automation-studio'))
    if (studioTarget) break
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  assert.ok(studioTarget, 'Studio second window opens')
  studio = await connectCdp(studioTarget.webSocketDebuggerUrl)
  const studioSidecar = await waitFor(studio, `(async()=>{const r=await window.autoflow.getRuntimeContext(); return r.sidecar.state==='ready'?r.sidecar.instanceId:null})()`, 'Studio shares ready sidecar', 30_000)
  assert.equal(studioSidecar, sidecar.instanceId)
  studio.close()
  await native.evaluate("pm9Electron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('view=automation-studio')).close()")
  report.checks.push('200% native window zoom keeps document within viewport; Studio second window shares the authenticated service')
  native.close()
  cdp.close()
  await stop(desktop.child)
  const restarted = await launch()
  const saved = await fetch(`${restarted.baseUrl}/api/v1${report.tablePath}`, { headers: { 'x-autoflow-token': restarted.token } })
  assert.equal(saved.status, 200)
  assert.equal((await saved.json()).recordCount, 1)
  await click('项目')
  await click('全部项目')
  await waitFor(cdp, "document.body.innerText.includes('PM9 桌面项目')", 'project after app restart')
  await capture('restarted')
  report.checks.push('Electron and its production sidecar restart retain the same data')
  report.status = 'passed'
} catch (error) {
  report.error = String(error.stack ?? error)
  // Preserve the disposable service's failure evidence before removing its workspace.
  report.sidecarLog = await readFile(join(userData, 'logs/sidecar.log'), 'utf8').then(log => redactSidecarLog(log, sidecar?.token)).catch(() => 'sidecar log unavailable')
  await capture('failure').catch(() => {})
  throw error
} finally {
  studio?.close()
  native?.close()
  cdp?.close()
  await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
  if (options['output-dir']) {
    await mkdir(options['output-dir'], { recursive: true })
    await writeFile(join(options['output-dir'], 'project-desktop.json'), JSON.stringify(report, null, 2))
  }
  console.log(JSON.stringify(report, null, 2))
}
