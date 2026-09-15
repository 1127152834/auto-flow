import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, lstat, mkdir, mkdtemp, readFile, readdir, realpath, stat, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { createInterface } from 'node:readline/promises'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')
export function parseQaArgs(args) {
  const result = { manual: false, prepareOnly: false, selfTest: false, kernelDirectory: undefined, scenario: 'success' }
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index]
    if (value === '--manual') result.manual = true
    else if (value === '--prepare-only') result.prepareOnly = true
    else if (value === '--self-test') result.selfTest = true
    else if (value === '--scenario') {
      const scenario = args[++index]
      if (!['success', 'failure', 'stop', 'recovery', 'restart', 'isolation'].includes(scenario)) throw new Error('--scenario must be success, failure, stop, recovery, restart, or isolation')
      result.scenario = scenario
    }
    else if (value === '--kernel-directory') {
      if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error('--kernel-directory requires a path')
      result.kernelDirectory = resolve(args[++index])
    } else throw new Error(`unknown argument: ${value}`)
  }
  return result
}

export function isOwnedQaWorkspace(path, ownerPath, marker) {
  return marker?.kind === 'pm3-project-management-qa' && within(resolve(path), resolve(ownerPath))
}

export const scenarioPlans = Object.freeze({
  success: ['UI创建项目与自动化', '启动两个真实浏览器任务', '核对批次、任务、日志、输入与输出'],
  failure: ['UI创建缺失点击目标的自动化', '启动真实浏览器任务并等待失败', '打开异常证据中的真实PNG预览'],
  stop: ['UI创建慢响应自动化', '启动两个任务', 'UI普通停止并确认', '核对全部取消且浏览器临时目录清理'],
  recovery: ['UI提交启动请求后丢弃响应与首次原键查询', '用原Idempotency-Key核对结果', '确认只创建一个批次'],
  restart: ['UI创建并完成批次', '关闭并重启Electron与后端', '通过重启后的真实服务读取持久批次并确认网页动作未重放'],
  isolation: ['在两个marker所有的独立workspace分别启动', '分别通过UI创建项目、自动化与批次', '核对workspace、项目与批次身份互不相同'],
})

const options = parseQaArgs(process.argv.slice(2))
const { manual, prepareOnly } = options
if (options.selfTest) {
  const testOwner = resolve(tmpdir(), 'pm3-qa-owner')
  assert.equal(isOwnedQaWorkspace(join(testOwner, 'workspace'), testOwner, { kind: 'pm3-project-management-qa' }), true)
  assert.equal(isOwnedQaWorkspace(resolve(testOwner, '..', 'other'), testOwner, { kind: 'pm3-project-management-qa' }), false)
  assert.equal(isOwnedQaWorkspace(join(testOwner, 'workspace'), testOwner, { kind: 'wrong-marker' }), false)
  assert.notDeepEqual(scenarioPlans.stop, scenarioPlans.recovery)
  console.log('qa helper self-test passed')
  process.exit(0)
}

if (options.scenario === 'isolation' && !options.prepareOnly) {
  const results = []
  for (let index = 0; index < 2; index += 1) {
    const { stdout } = await exec(process.execPath, [new URL(import.meta.url).pathname, '--scenario', 'success', ...(options.kernelDirectory ? ['--kernel-directory', options.kernelDirectory] : [])], { cwd: root, maxBuffer: 10_000_000 })
    results.push(JSON.parse(stdout.slice(stdout.indexOf('{'))))
  }
  assert.notEqual(results[0].workspace, results[1].workspace)
  assert.notEqual(results[0].uiResult.projectId, results[1].uiResult.projectId)
  assert.notEqual(results[0].uiResult.batchId, results[1].uiResult.batchId)
  for (const result of results) {
    const marker = JSON.parse(await readFile(join(result.owner, '.pm3-project-management-qa.json'), 'utf8'))
    assert.ok(isOwnedQaWorkspace(result.workspace, result.owner, marker))
  }
  const directory = join(root, 'docs/project-management/implementation/pm3/qa-runs')
  await mkdir(directory, { recursive: true })
  const evidence = await mkdtemp(join(directory, 'isolation-'))
  const result = { status: 'passed', scenario: 'isolation', scenarioPlan: scenarioPlans.isolation, workspaces: results.map(item => ({ owner: item.owner, workspace: item.workspace, projectId: item.uiResult.projectId, batchId: item.uiResult.batchId, evidence: item.evidence })), createdAt: new Date().toISOString() }
  await writeFile(join(evidence, 'result.json'), JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); process.exit(0)
}

const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm3-run-qa-')))
const workspace = join(owner, 'workspace')
await mkdir(workspace)
await writeFile(join(owner, '.pm3-project-management-qa.json'), JSON.stringify({ kind: 'pm3-project-management-qa', createdAt: new Date().toISOString() }, null, 2))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))

const evidenceRoot = join(root, 'docs/project-management/implementation/pm3/qa-runs')
await mkdir(evidenceRoot, { recursive: true })
const evidence = await mkdtemp(join(evidenceRoot, 'run-'))
const screenshots = []
let desktop, renderer, native, fixture

function within(path, parent) {
  const offset = relative(parent, path)
  return offset !== '..' && !offset.startsWith(`..${sep}`) && !isAbsolute(offset)
}

async function findKernel() {
  const explicit = options.kernelDirectory
  const directory = explicit ? resolve(explicit) : join(homedir(), 'Library', 'Application Support', '@autoflow', 'desktop', 'data', 'kernels')
  const candidates = explicit ? [directory] : (await readdir(directory, { withFileTypes: true }).catch(() => []))
    .filter(entry => entry.isDirectory() && /^chromium-\d+(?:\.\d+){3,4}$/.test(entry.name))
    .map(entry => join(directory, entry.name)).sort().reverse()
  for (const candidate of candidates) {
    const source = await realpath(candidate).catch(() => undefined)
    if (!source || !(await lstat(source)).isDirectory()) continue
    const executable = kernelExecutablePath(source, process.platform)
    if ((await stat(executable).catch(() => undefined))?.isFile()) return { source, executable }
  }
  throw new Error('未找到已安装的公开版 CloakBrowser 内核；可传 --kernel-directory <chromium-version目录>')
}

async function copyKernel() {
  const kernel = await findKernel()
  const destination = join(workspace, 'data', 'kernels', basename(kernel.source))
  assert.ok(within(destination, owner), 'kernel destination must remain in the tool-owned workspace')
  await cp(kernel.source, destination, { recursive: true, dereference: false, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
  return { source: kernel.source, copiedTo: destination, version: basename(kernel.source).slice('chromium-'.length) }
}

async function startFixture() {
  const requests = []
  const server = createServer((request, response) => {
    requests.push({ method: request.method, url: request.url, at: new Date().toISOString() })
    const respond = () => {
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
      response.end(`<!doctype html><html lang="zh-CN"><body><label>验收输入<input id="field" value="before"></label><button id="button" data-clicked="no">确认</button><output id="result">等待点击</output><script>button.onclick=()=>{button.dataset.clicked='yes';result.textContent=field.value}</script></body></html>`)
    }
    if (request.url === '/slow') setTimeout(respond, 60_000)
    else respond()
  })
  await new Promise((resolveReady, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveReady) })
  const { port } = server.address()
  return { server, requests, url: `http://127.0.0.1:${port}/fixture`, slowUrl: `http://127.0.0.1:${port}/slow` }
}

async function dropStartResponseAndFirstLookup(runtime) {
  let droppedStart = false, droppedLookup = false, originalKey
  const listener = async event => {
    const message = JSON.parse(event.data)
    if (message.method !== 'Fetch.requestPaused') return
    const { requestId, request, responseStatusCode } = message.params
    const isStart = !droppedStart && request.method === 'POST' && /\/automations\/[^/]+\/batches$/.test(new URL(request.url).pathname) && responseStatusCode === 202
    const isLookup = droppedStart && !droppedLookup && request.url.includes('/operations/by-idempotency-key/')
    if (isStart || isLookup) {
      if (isStart) { droppedStart = true; originalKey = Object.entries(request.headers).find(([key]) => key.toLowerCase() === 'idempotency-key')?.[1] }
      else droppedLookup = true
      await renderer.command('Fetch.failRequest', { requestId, errorReason: 'ConnectionReset' })
    } else await renderer.command('Fetch.continueRequest', { requestId })
  }
  renderer.socket.addEventListener('message', listener)
  await renderer.command('Fetch.enable', { patterns: [{ urlPattern: `${runtime.sidecar.baseUrl}/api/v1/projects/*`, requestStage: 'Response' }] })
  return async () => {
    await renderer.command('Fetch.disable'); renderer.socket.removeEventListener('message', listener)
    assert.ok(droppedStart && droppedLookup && originalKey, 'recovery injection must drop the accepted response and first original-key lookup')
    return originalKey
  }
}

async function hashes() {
  const digest = createHash('sha256')
  for (const sourceRoot of ['apps/desktop/src', 'apps/backend/src']) {
    for (const name of (await readdir(join(root, sourceRoot), { recursive: true })).filter(name => /\.(tsx?|css|py)$/.test(name)).sort()) {
      digest.update(`${sourceRoot}/${name}`).update(await readFile(join(root, sourceRoot, name)))
    }
  }
  return { sourceSha256: digest.digest('hex'), head: (await exec('git', ['rev-parse', 'HEAD'], { cwd: root })).stdout.trim() }
}

async function capture(name) {
  const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
  const file = join(evidence, `${name}.png`)
  await writeFile(file, Buffer.from(data, 'base64'))
  screenshots.push({ name, file, sha256: createHash('sha256').update(Buffer.from(data, 'base64')).digest('hex') })
}

async function seedWorkflow(workspaceKey, url, scenario) {
  const workflowId = randomUUID()
  const parameterId = randomUUID()
  const code = `from pathlib import Path
from uuid import uuid4
import sys
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.filesystem.paths import AppPaths
from tests.fixtures.workflows import workflow_payload
factory=create_session_factory(AppPaths.from_data_dir(Path(sys.argv[1])).database)
document=workflow_payload(sys.argv[2]); document['content']['name']='PM3真实运行验收流程'
nodes=document['content']['nodes']; nodes[0]['data']['url']=sys.argv[3]
nodes[1]['data'].update(selector='#field',text='真实点击输入',clearBefore=False)
nodes[2]['data']['selector']='#button'; nodes[3]['data'].update(selector='#button',attribute='data-clicked')
if sys.argv[5]=='failure': nodes[2]['data'].update(selector='#missing-submit',timeout=1)
nodes.append({'id':'read-input','type':'get_element_info','position':{'x':100,'y':560},'data':{'moduleType':'get_element_info','selector':'#field','attribute':'value','variableName':'实际输入'}})
document['content']['edges'].append({'id':'edge-input-read','source':'read','target':'read-input'})
created=WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(document,str(uuid4()))
print(created.workflow_id); factory.dispose()`
  const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, workspaceKey, workflowId, url, parameterId, scenario], { cwd: root })
  return { workflowId: stdout.trim(), parameterId, preparation: '工作流文档通过 WorkflowService 预置；Studio 不在本次验收范围。项目与自动化必须通过 UI 创建。' }
}

async function seedProfile(runtime, browserVersion) {
  const profile = await api(runtime, '/profiles', { method: 'POST', body: { name: 'PM3真实运行浏览器', description: 'QA资源资料', startUrl: 'about:blank', locale: null, timezone: null, geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: null, extensionPathsJson: [], expertArgsJson: [], browserVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null } })
  return { profileId: profile.id, preparation: '浏览器配置通过真实 HTTP ProfileService API 预置为运行资源夹具；项目与自动化仍由 UI 创建。' }
}

async function click(text, selector = 'button') {
  const point = await waitFor(renderer, `(()=>{const visibleText=e=>{const c=e.cloneNode(true);c.querySelectorAll('[aria-hidden=true]').forEach(n=>n.remove());return c.textContent.trim()};const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled&&(visibleText(e)===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}||e.labels?.[0]?.textContent.trim()===${JSON.stringify(text)}));if(items.length!==1)return null;const e=items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),x=${JSON.stringify(selector)}==='[role=option]'?r.x+12:r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `control ${text}`)
  for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
  await wait(120)
}

async function clickRowButton(rowText, buttonText) {
  const point = await waitFor(renderer, `(()=>{const row=[...document.querySelectorAll('tbody tr')].find(e=>e.textContent.includes(${JSON.stringify(rowText)}));const e=row&&[...row.querySelectorAll('button')].find(e=>e.textContent.includes(${JSON.stringify(buttonText)}));if(!e||e.disabled)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `row ${rowText} button ${buttonText}`)
  for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
  await wait(120)
}

async function input(selector, value) {
  await waitFor(renderer, `!!document.querySelector(${JSON.stringify(selector)})`, selector)
  await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.focus();e.select();return true})()`)
  await renderer.command('Input.insertText', { text: value })
}

async function chooseNextOption(triggerLabel) {
  await click(triggerLabel, '[role=combobox]')
  for (const key of ['ArrowDown', 'Enter']) {
    await renderer.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: key === 'Enter' ? 13 : 40 })
    await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: key === 'Enter' ? 13 : 40 })
  }
  await wait(120)
}

async function api(runtime, path, { method = 'GET', body } = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, { method, headers: { 'x-autoflow-token': runtime.sidecar.token, ...(body ? { 'content-type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(10_000) })
  const text = await response.text()
  assert.ok(response.ok, `${path}: ${response.status} ${text}`)
  return JSON.parse(text)
}

async function assertEditorIdle(stage) {
  const state = await renderer.evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(e=>e.textContent.includes('保存配置'));return b?{disabled:b.disabled,busy:b.getAttribute('aria-busy'),text:b.textContent}:null})()`)
  assert.ok(state && !state.disabled && state.busy !== 'true', `${stage} unexpectedly locked save: ${JSON.stringify(state)}`)
}

async function waitBatchTerminal(runtime, projectId, batchId) {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const detail = await api(runtime, `/projects/${projectId}/batches/${batchId}`)
    if (['completed', 'failed', 'stopped', 'interrupted'].includes(detail.batch.status)) return detail
    await wait(200)
  }
  throw new Error(`batch ${batchId} did not reach a terminal persisted status`)
}

async function runUiSuccessChain(runtime, workflow, profile, scenario = 'success') {
  await click('项目'); await click('新建项目')
  await input('#project-name', 'PM3运行验收项目'); await input('#project-description', '真实浏览器批次与证据验收'); await click('创建项目')
  await waitFor(renderer, "document.body.innerText.includes('项目资料')", 'created project')
  const project = (await api(runtime, '/projects?q=PM3运行验收项目')).items[0]
  await click('自动化', '[aria-label="项目功能"] button')
  await waitFor(renderer, "document.querySelector('[aria-label=\"项目功能\"] [aria-current=page]')?.textContent.trim()==='自动化'", 'automation project tab')
  await waitFor(renderer, "document.body.innerText.includes('还没有自动化') || document.querySelector('[data-testid=automation-grid]')", 'automation directory')
  await click('新建自动化')
  await input('[aria-label="自动化名称"]', '参数运行验收'); await input('[aria-label="用途说明"]', '真实输入、点击、输出与日志证据')
  await click('关联工作流', '[role=combobox]'); await click('PM3真实运行验收流程', '[role=option]')
  await assertEditorIdle('workflow selection')
  await click('输入与参数', '[role=tab]'); await click('新增参数')
  await input('[aria-label^="参数名称 "]', '数量')
  await waitFor(renderer, "!!document.querySelector('[aria-label=\"参数类型 数量\"]')", 'quantity parameter')
  await click('参数类型 数量', '[role=combobox]'); await click('数字', '[role=option]'); await click('新增参数')
  await waitFor(renderer, "document.querySelectorAll('[aria-label^=\"参数名称 \"]').length===2", 'second parameter')
  const names = await renderer.evaluate("[...document.querySelectorAll('[aria-label^=\"参数名称 \"]')].map(e=>e.getAttribute('aria-label'))")
  await input(`[aria-label=${JSON.stringify(names.at(-1))}]`, '备注')
  await assertEditorIdle('parameter editing')
  await click('资源与环境', '[role=tab]'); await chooseNextOption('浏览器配置来源')
  await waitFor(renderer, "document.querySelector('[aria-label=\"浏览器配置来源\"]')?.textContent.includes('指定浏览器配置')", 'specified profile source')
  await assertEditorIdle('profile source selection')
  await chooseNextOption('浏览器配置')
  await waitFor(renderer, "document.querySelector('[aria-label=\"浏览器配置\"]')?.textContent.includes('PM3真实运行浏览器')", 'profile selected')
  await assertEditorIdle('profile selection')
  await click('保存配置')
  await waitFor(renderer, "document.body.innerText.includes('自动化已创建')", 'automation created')
  await capture('01-automation')
  await click('启动运行'); await waitFor(renderer, "document.body.innerText.includes('启动自动化')", 'batch launcher')
  await input('[aria-label="数量"]', '0'); await input('[aria-label="备注"]', '保留 false/0/null 语义')
  await input('[aria-label="本次任务数"]', '2'); await capture('02-start-batch')
  const stopInjection = scenario === 'recovery' ? await dropStartResponseAndFirstLookup(runtime) : undefined
  await click('启动 2 个任务')
  let recoveryKey
  if (stopInjection) {
    await waitFor(renderer, "document.body.innerText.includes('批次操作已接受') || document.body.innerText.includes('核对原操作')", 'unknown start result', 30_000)
    await capture('03-unknown-start'); recoveryKey = await stopInjection(); await click('核对原操作')
  }
  await waitFor(renderer, "document.body.innerText.includes('本批次任务')", 'batch detail', 30_000)
  await capture('04-batch-detail')
  const batches = await api(runtime, `/projects/${project.projectId}/batches?pageSize=20`)
  const batch = batches.items[0]
  if (scenario === 'recovery') { assert.equal(batches.total, 1); assert.ok(recoveryKey) }
  if (scenario === 'stop') {
    await click('停止批次'); await waitFor(renderer, "document.body.innerText.includes('停止当前批次？')", 'stop confirmation')
    await input('[aria-label="停止原因"]', 'PM3真实普通停止验收'); await capture('03-stop-confirmation'); await click('确认停止')
    const stopped = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
    assert.equal(stopped.batch.status, 'stopped')
    assert.equal(stopped.statusCounts.cancelled, 2)
    await waitFor(renderer, "document.body.innerText.includes('已停止')", 'stopped batch projection', 10_000)
    await capture('04-stopped-batch')
    const tasks = await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)
    assert.equal(tasks.total, 2); assert.ok(tasks.items.every(item => item.status === 'cancelled'))
    return { projectId: project.projectId, automationName: '参数运行验收', batchId: batch.batchId, taskIds: tasks.items.map(item => item.taskId), profileId: profile.profileId, stop: 'ordinary', status: stopped.batch.status }
  }
  const detail = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
  assert.equal(detail.batch.requestedCount, 2)
  assert.equal(Object.values(detail.statusCounts).reduce((sum, value) => sum + value, 0), 2)
  if (scenario === 'success') {
    assert.equal(detail.statusCounts.succeeded, 2)
    await waitFor(renderer, "document.body.innerText.includes('成功 2')", 'terminal batch projection', 10_000)
  }
  const tasks = await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)
  const selectedTask = scenario === 'failure' ? tasks.items.find(item => item.status === 'failed' || item.status === 'timed_out') : tasks.items[0]
  assert.ok(selectedTask)
  await clickRowButton(selectedTask.taskId, '查看任务'); await waitFor(renderer, "document.body.innerText.includes('输入与输出')", 'task detail')
  await capture('05-task-logs'); await click('输入与输出', '[role=tab]'); await capture('06-task-input-output')
  await click('异常与证据', '[role=tab]'); await capture('07-task-evidence')
  assert.equal(tasks.total, 2)
  const task = await api(runtime, `/projects/${project.projectId}/tasks/${selectedTask.taskId}`)
  assert.deepEqual(Object.values(task.inputSnapshot.parameters).sort((left, right) => String(left).localeCompare(String(right))), [0, '保留 false/0/null 语义'])
  assert.ok(fixture.requests.length >= (scenario === 'success' ? 2 : 1), 'real browser tasks must request the local fixture')
  if (scenario === 'failure') {
    assert.ok(['failed', 'timed_out'].includes(task.task.status))
    const artifacts = await api(runtime, `/projects/${project.projectId}/tasks/${task.task.taskId}/artifacts?page=1&pageSize=100`)
    const screenshot = artifacts.items.find(item => item.kind === 'screenshot' && item.availability === 'available')
    assert.ok(screenshot?.mediaType === 'image/png' && screenshot.byteSize > 0)
    if (!(await renderer.evaluate(`!!document.querySelector('[aria-label=${JSON.stringify(`查看失败截图：${screenshot.nodeId}`)}]')`))) {
      await click('← 返回批次'); await clickRowButton(selectedTask.taskId, '查看任务'); await click('异常与证据', '[role=tab]')
    }
    await click(`查看失败截图：${screenshot.nodeId}`)
    await waitFor(renderer, `!!document.querySelector('img[alt=${JSON.stringify(`失败截图：${screenshot.nodeId}`)}]')`, 'failure PNG preview')
    await capture('08-failure-preview')
  }
  return { projectId: project.projectId, automationName: '参数运行验收', batchId: batch.batchId, taskIds: tasks.items.map(item => item.taskId), profileId: profile.profileId, ...(recoveryKey ? { recoveryKey } : {}) }
}

async function close() {
  renderer?.close(); native?.close()
  await stop(desktop?.child)
  if (fixture) await new Promise(resolveClose => fixture.server.close(resolveClose))
}

try {
  const kernel = await copyKernel()
  fixture = await startFixture()
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.pm3Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm3Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
  await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(renderer, "document.body.innerText.includes('本地服务正常')", 'local backend ready', 30_000)
  let runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  assert.ok(isOwnedQaWorkspace(runtime.workspaceKey, owner, { kind: 'pm3-project-management-qa' }), 'Only the marker-owned workspace may be changed')
  const workflow = await seedWorkflow(runtime.workspaceKey, options.scenario === 'stop' ? fixture.slowUrl : fixture.url, options.scenario)
  const profile = await seedProfile(runtime, kernel.version)
  await capture('00-prepared')
  if (!prepareOnly && !['success', 'failure', 'stop', 'recovery', 'restart'].includes(options.scenario)) throw new Error(`scenario ${options.scenario} is planned but not yet wired to UI actions; no run fact was created`)
  let uiResult
  try {
    uiResult = prepareOnly ? undefined : await runUiSuccessChain(runtime, workflow, profile, options.scenario === 'restart' ? 'success' : options.scenario)
  } catch (error) {
    await capture('99-failure')
    const failure = { status: 'failed', scenario: options.scenario, message: error instanceof Error ? error.message : String(error), url: await renderer.evaluate('location.href'), bodyText: await renderer.evaluate('document.body.innerText'), screenshots, createdAt: new Date().toISOString() }
    await writeFile(join(evidence, 'result.json'), JSON.stringify(failure, null, 2))
    console.error(`QA_FAILURE_EVIDENCE ${join(evidence, 'result.json')}`)
    throw error
  }
  if (!prepareOnly && options.scenario === 'restart') {
    const requestsBefore = fixture.requests.length
    renderer.close(); native.close(); await stop(desktop.child)
    desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] }); renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
    await waitFor(renderer, "document.body?.innerText?.includes('本地服务正常')", 'restarted backend ready', 30_000)
    runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    assert.ok(isOwnedQaWorkspace(runtime.workspaceKey, owner, { kind: 'pm3-project-management-qa' }))
    const persisted = await api(runtime, `/projects/${uiResult.projectId}/batches/${uiResult.batchId}`)
    assert.equal(persisted.batch.status, 'completed'); await wait(1500); assert.equal(fixture.requests.length, requestsBefore)
    await capture('08-after-restart')
    uiResult = { ...uiResult, restart: { persistedStatus: persisted.batch.status, requestsBefore, requestsAfter: fixture.requests.length } }
  }
  const result = { status: prepareOnly ? 'prepared' : 'passed', scenario: options.scenario, scenarioPlan: scenarioPlans[options.scenario], ...(await hashes()), owner, workspace, evidence, kernel, fixtureUrl: fixture.url, slowFixtureUrl: fixture.slowUrl, workflow, profile, uiResult, screenshots, next: prepareOnly ? scenarioPlans[options.scenario] : [], commands: { success: 'node scripts/qa-project-management-pm3.mjs --scenario success', manual: 'node scripts/qa-project-management-pm3.mjs --manual --scenario success', preparation: 'node scripts/qa-project-management-pm3.mjs --prepare-only --scenario success', explicitKernel: 'node scripts/qa-project-management-pm3.mjs --manual --kernel-directory /path/to/chromium-x.y.z.w' }, createdAt: new Date().toISOString() }
  await writeFile(join(evidence, 'result.json'), JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
  if (manual && !prepareOnly) {
    console.log('应用保持打开。项目与自动化请从 UI 创建；输入 s 截图，q 退出。')
    const cli = createInterface({ input: process.stdin, output: process.stdout })
    for (;;) {
      const command = (await cli.question('pm3-qa> ')).trim()
      if (command === 'q') break
      if (command === 's') await capture(`manual-${String(screenshots.length).padStart(2, '0')}`)
    }
    cli.close()
  }
} finally {
  await close()
}
