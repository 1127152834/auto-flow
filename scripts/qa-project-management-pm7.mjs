#!/usr/bin/env node
/**
 * PM7 management-side acceptance harness.
 *
 * Runs real Electron + FastAPI + SQLite + the isolated QA executor
 * (`tests.qa.pm7_sidecar`, reachable only through the development QA switch) and
 * drives the product through the renderer. Nothing here touches Studio, and no
 * production route is added for testing.
 *
 * Boundary: 管理侧通过，真实执行核心接入待验收。
 */
import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, lstat, mkdir, mkdtemp, readdir, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { pathToFileURL } from 'node:url'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage, waitForSelector } from './electron-cdp.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')

export const PM7_FAULT_KINDS = Object.freeze([
  'overview-read-failure',
  'statistics-read-failure',
  'statistics-ttl',
  'followup-conflict',
  'response-loss',
  'late-event',
  'executor-fail',
  'executor-pause',
  'executor-resume',
])

export const PM7_STEPS = Object.freeze([
  'E2E-1 概览事实：界面创建项目/三表/自动化并跑出成功、失败与停止结果',
  'E2E-2 统计与下钻：四指标、口径、失败去向、冻结集合下钻与刷新',
  'E2E-3 失败后续：从原输入组发起后续批次并保留来源任务',
  'E2E-4 任务证据：原始输入、当前值对照、数据写入与节点日志',
  'E2E-5 异常：概览读取失败、统计结果集过期、修订冲突、响应丢失、迟到事件',
  'E2E-6 边界：200% 缩放与长文本不撑宽（双工作区切换见手测 M-12）',
])

export function parsePm7QaArgs(args) {
  const result = { manual: false, prepareOnly: false, selfTest: false, cleanupOnly: false, workspace: undefined, inject: [] }
  for (const value of args) {
    if (value === '--manual') result.manual = true
    else if (value === '--prepare-only') result.prepareOnly = true
    else if (value === '--self-test') result.selfTest = true
    else if (value === '--cleanup-only') result.cleanupOnly = true
    else if (value.startsWith('--workspace=')) result.workspace = value.slice('--workspace='.length)
    else if (value.startsWith('--inject=')) result.inject.push(value.slice('--inject='.length))
    else throw new Error(`unknown argument: ${value}`)
  }
  for (const kind of result.inject) {
    if (!PM7_FAULT_KINDS.includes(kind) && kind !== 'service-restart') throw new Error(`unknown fault injection: ${kind}`)
  }
  return result
}

export function isOwnedPm7Workspace(path, ownerPath, marker) {
  const offset = relative(resolve(ownerPath), resolve(path))
  return marker?.kind === 'pm7-project-management-qa'
    && marker?.version === 1
    && marker?.runId === marker?.runId
    && offset !== '..'
    && !offset.startsWith(`..${sep}`)
    && !isAbsolute(offset)
}

function canonicalRecord(record) {
  return {
    ref: record.ref,
    values: record.values,
    statusId: record.statusId,
    contentRevision: record.contentRevision,
    statusRevision: record.statusRevision,
    linkRevision: record.linkRevision,
  }
}

export async function main(cliArgs = process.argv.slice(2)) {
  const options = parsePm7QaArgs(cliArgs)
  if (options.selfTest) {
    assert.equal(isOwnedPm7Workspace('/tmp/pm7-owner/workspace', '/tmp/pm7-owner', { kind: 'pm7-project-management-qa', version: 1, runId: 'r' }), true)
    assert.equal(isOwnedPm7Workspace('/tmp/pm7-other/workspace', '/tmp/pm7-owner', { kind: 'pm7-project-management-qa', version: 1, runId: 'r' }), false)
    assert.equal(isOwnedPm7Workspace('/tmp/pm7-owner/workspace', '/tmp/pm7-owner', { kind: 'pm4-v1-project-management-qa', version: 1 }), false)
    assert.equal(PM7_STEPS.length, 6)
    assert.equal(PM7_FAULT_KINDS.length, 9)
    assert.deepEqual(parsePm7QaArgs(['--manual', '--inject=statistics-ttl']), { manual: true, prepareOnly: false, selfTest: false, cleanupOnly: false, workspace: undefined, inject: ['statistics-ttl'] })
    assert.throws(() => parsePm7QaArgs(['--inject=nope']))
    console.log('PM7 QA helper self-test passed')
    return
  }

  if (options.cleanupOnly) {
    const target = options.workspace
    assert.ok(target, '--cleanup-only 需要 --workspace=<隔离工作区路径>')
    const ownerPath = resolve(target, '..')
    const marker = await readFile(join(ownerPath, '.pm7-qa.json'), 'utf8').then(JSON.parse, () => undefined)
    assert.ok(isOwnedPm7Workspace(target, ownerPath, marker), '只清理带 PM7 QA 所有权标记的目录')
    await rm(ownerPath, { recursive: true, force: true })
    console.log(`已清理 PM7 QA 隔离目录 ${ownerPath}`)
    return
  }

  const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
  const owner = await realpath(await mkdtemp(join(tmpdir(), `autoflow-pm7-qa-${runId}-`)))
  const workspace = options.workspace ? resolve(options.workspace) : join(owner, 'workspace')
  const marker = { kind: 'pm7-project-management-qa', version: 1, runId, createdAt: new Date().toISOString() }
  if (options.workspace) {
    assert.ok(await stat(workspace).then(() => true, () => false), '--workspace 必须已存在')
  } else {
    await mkdir(workspace)
    await writeFile(join(owner, '.pm7-qa.json'), JSON.stringify(marker, null, 2))
    await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
    await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))
  }

  const evidence = join(root, 'docs/project-management/implementation/pm7/qa-runs', runId)
  await mkdir(evidence, { recursive: true })
  const screenshots = []
  const checkpoints = []
  const boundary = { executor: 'isolatedQaExecutor', browser: 'notExecuted', studio: 'notExecuted' }
  let desktop
  let renderer
  let native

  const checkpoint = message => { checkpoints.push(message); console.log(`✓ ${message}`) }
  const report = async (status, error, facts) => {
    const { stdout: head } = await exec('git', ['rev-parse', 'HEAD'], { cwd: root })
    const sourceHash = createHash('sha256')
    for (const path of ['apps/backend/src', 'apps/desktop/src']) {
      for (const name of (await readdir(join(root, path), { recursive: true })).filter(name => /\.(py|tsx?|css)$/.test(name)).sort()) {
        sourceHash.update(`${path}/${name}`).update(await readFile(join(root, path, name)))
      }
    }
    const result = {
      status,
      scenario: 'PM7-A management-side overview/statistics/evidence/follow-up',
      scope: status === 'passed' ? '管理侧通过，真实执行核心接入待验收' : 'PM7 A 管理侧验收未通过',
      boundary,
      steps: PM7_STEPS,
      visualReview: 'pending',
      injected: injections,
      gitHead: head.trim(),
      sourceSha256: sourceHash.digest('hex'),
      platform: process.platform,
      arch: process.arch,
      runId,
      owner,
      workspace,
      evidence,
      checkpoints,
      screenshots,
      network: await recordedNetwork(),
      facts,
      error,
      excluded: ['真实执行核心', 'Studio demo', '真实浏览器执行', 'Windows', '其他架构', '打包应用', '用户手动执行结果', '双工作区切换（见手测 M-12）'],
      createdAt: new Date().toISOString(),
    }
    await writeFile(join(evidence, 'report.json'), `${JSON.stringify(result, null, 2)}\n`)
    return result
  }

  const injections = []
  // Every mutation the renderer really sends is recorded, so a failure carries the
  // actual HTTP outcome instead of a re-derived guess. Evidence only; it changes no request.
  const installNetworkRecorder = () => renderer.evaluate(`(()=>{if(globalThis.__pm7Network)return true;globalThis.__pm7Network=[];const original=globalThis.fetch.bind(globalThis);globalThis.fetch=async(input,init)=>{const response=await original(input,init);try{const url=typeof input==='string'?input:(input?.url??'');const method=(init?.method??'GET').toUpperCase();if(String(url).includes('/api/v1/')&&(method!=='GET'||!response.ok)){let body='';try{body=(await response.clone().text()).slice(0,2000)}catch{}globalThis.__pm7Network.push({method,url:String(url),status:response.status,body})}}catch{}return response};return true})()`)
  const recordedNetwork = async () => (renderer ? await renderer.evaluate('globalThis.__pm7Network ?? []').catch(() => []) : [])
  const assertOwned = runtime => assert.ok(isOwnedPm7Workspace(runtime.workspaceKey, owner, marker), 'QA 只能修改带所有权标记的隔离工作区')

  async function launch() {
    const previous = {
      module: process.env.AUTOFLOW_QA_SIDECAR_MODULE,
      pm4: process.env.AUTOFLOW_PM4_QA,
      mode: process.env.AUTOFLOW_PM4_QA_MODE,
      maxAutoTasks: process.env.AUTOFLOW_PM4_QA_MAX_AUTO_TASKS,
    }
    process.env.AUTOFLOW_QA_SIDECAR_MODULE = 'tests.qa.pm7_sidecar'
    delete process.env.AUTOFLOW_PM4_QA
    process.env.AUTOFLOW_PM4_QA_MODE = 'f'
    process.env.AUTOFLOW_PM4_QA_MAX_AUTO_TASKS = '5'
    try {
      desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
    } finally {
      for (const [key, value] of Object.entries({ AUTOFLOW_QA_SIDECAR_MODULE: previous.module, AUTOFLOW_PM4_QA: previous.pm4, AUTOFLOW_PM4_QA_MODE: previous.mode, AUTOFLOW_PM4_QA_MAX_AUTO_TASKS: previous.maxAutoTasks })) {
        if (value === undefined) delete process.env[key]
        else process.env[key] = value
      }
    }
    renderer = desktop.cdp
    native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate("globalThis.pm7Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm7Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await visible('本地服务正常', 30_000)
    const runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    await installNetworkRecorder()
    assertOwned(runtime)
    return runtime
  }

  async function shutdown() {
    renderer?.close()
    native?.close()
    await stop(desktop?.child)
    renderer = native = desktop = undefined
  }

  async function visible(text, timeout = 15_000) {
    return waitFor(renderer, `document.body?.innerText?.includes(${JSON.stringify(text)})`, text, timeout)
  }

  async function click(text, selector = 'button') {
    if (selector === '[role=tab]') text = ({ 记录: '数据记录', 字段: '字段与校验', 状态: '数据状态', 来源: '来源设置', 设置: '数据表设置' })[text] ?? text
    const point = await waitFor(renderer, `(()=>{const visible=e=>{const s=getComputedStyle(e);return e.getClientRects().length&&!e.disabled&&s.display!=='none'&&s.visibility!=='hidden'&&s.pointerEvents!=='none'};const label=e=>{if(e.getAttribute('aria-label'))return e.getAttribute('aria-label');const copy=e.cloneNode(true);copy.querySelectorAll?.('[aria-hidden=true]').forEach(node=>node.remove());return copy.textContent.trim()};const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>visible(e)&&(${JSON.stringify(text)}===''||label(e)===${JSON.stringify(text)}));if(!items.length)return null;const hit=e=>{const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return x>=0&&x<=innerWidth&&y>=0&&y<=innerHeight&&e.contains(document.elementFromPoint(x,y))};const e=items.find(hit)??items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `${selector} ${text}`)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(140)
  }

  async function clickNth(selector, index) {
    const point = await waitFor(renderer, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled)[${index}];if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `${selector}[${index}]`)
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(140)
  }

  async function doubleClick(selector) {
    const point = await waitFor(renderer, `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||!e.getClientRects().length)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, selector)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    await renderer.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 2 })
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 2 })
    await wait(140)
  }

  async function input(selector, value, index = 0) {
    await waitFor(renderer, `document.querySelectorAll(${JSON.stringify(selector)}).length>${index}`, selector)
    await renderer.evaluate(`(()=>{const e=document.querySelectorAll(${JSON.stringify(selector)})[${index}];e.scrollIntoView({block:'center'});e.focus();e.select();true})()`)
    await renderer.command('Input.insertText', { text: value })
    await wait(80)
  }

  async function pressKey(key) {
    const code = key === 'Enter' ? 'Enter' : key === 'Escape' ? 'Escape' : key
    const virtualKeyCode = key === 'Enter' ? 13 : key === 'Escape' ? 27 : undefined
    const event = { key, code, ...(virtualKeyCode ? { windowsVirtualKeyCode: virtualKeyCode, nativeVirtualKeyCode: virtualKeyCode } : {}), ...(key === 'Enter' ? { text: '\r', unmodifiedText: '\r' } : {}) }
    await renderer.command('Input.dispatchKeyEvent', { type: key === 'Enter' ? 'keyDown' : 'rawKeyDown', ...event })
    await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', ...event })
    await wait(120)
  }

  const settle = () => new Promise(resolve => setTimeout(resolve, 2800))

  async function capture(name, reference) {
    await settle()
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate(`({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})`)
    assert.ok(geometry.scrollWidth <= geometry.viewport.width + 1, `${name} 不能撑宽应用`)
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    const bytes = Buffer.from(data, 'base64')
    const file = join(evidence, `${name}.png`)
    await writeFile(file, bytes)
    screenshots.push({ name, file, reference, ...geometry, sha256: createHash('sha256').update(bytes).digest('hex'), visualReview: 'pending' })
    console.log(`  · 截图 ${name} → ${reference ?? '（无对应画板）'}`)
  }

  async function api(runtime, path) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token }, signal: AbortSignal.timeout(15_000) })
    const body = await response.text()
    assert.ok(response.ok, `GET ${path}: ${response.status} ${body}`)
    return JSON.parse(body)
  }

  async function fault(runtime, kind, body = {}) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1/qa/pm7/fault`, {
      method: 'POST',
      headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json' },
      body: JSON.stringify({ kind, ...body }),
      signal: AbortSignal.timeout(15_000),
    })
    const text = await response.text()
    assert.ok(response.ok, `注入 ${kind}: ${response.status} ${text}`)
    const result = JSON.parse(text)
    injections.push({ ...result, at: new Date().toISOString() })
    return result
  }

  /** 手动模式的重启入口：真实停掉并拉起 sidecar，等新实例 ready。 */
  async function restartService() {
    const previous = await renderer.evaluate('(async()=> (await window.autoflow.getRuntimeContext()).sidecar.instanceId)()')
    await renderer.evaluate('window.autoflow.restartSidecar()')
    await waitFor(renderer, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(previous)}})()`, 'service restarts', 30_000)
    await visible('本地服务正常', 30_000)
    checkpoint('测试服务完整重启并等待新实例 ready。')
  }

  /** 手动模式：等到流程跑完再注入，确保失败任务等事实已存在。 */
  async function applyManualInjections() {
    for (const kind of options.inject) {
      if (kind === 'service-restart') { await restartService(); continue }
      const needsTask = kind === 'followup-conflict' || kind === 'late-event'
      await fault(runtime, kind, needsTask ? { taskId: failedTaskId } : {})
      console.log(`已注入 ${kind}（测试注入，记录在 report.json 的 injected 字段）。`)
    }
  }

  async function faultState(runtime) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1/qa/pm7/state`, { headers: { 'x-autoflow-token': runtime.sidecar.token }, signal: AbortSignal.timeout(10_000) })
    assert.ok(response.ok, `QA state: ${response.status}`)
    return response.json()
  }

  async function seedWorkflow(runtime, name) {
    const workflowId = randomUUID()
    const code = `from pathlib import Path
from uuid import uuid4
import sys
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.filesystem.paths import AppPaths
from tests.fixtures.workflows import workflow_payload
factory=create_session_factory(AppPaths.from_data_dir(Path(sys.argv[1])).database)
document=workflow_payload(sys.argv[2]); document['content']['name']=sys.argv[3]
created=WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(document,str(uuid4()))
print(created.workflow_id); factory.dispose()`
    const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, runtime.workspaceKey, workflowId, name], { cwd: root })
    return stdout.trim()
  }

  async function seedProfile(runtime) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1/profiles`, {
      method: 'POST',
      headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json' },
      body: JSON.stringify({ name: 'PM7 隔离执行器资源', description: '仅作为管理端资源夹具', startUrl: 'about:blank', locale: null, timezone: null, geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: null, extensionPathsJson: [], expertArgsJson: [], browserVersion: runtime.qaKernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null }),
    })
    assert.ok(response.ok, `profile fixture failed: ${response.status} ${response.ok ? '' : await response.text()}`)
    return (await response.json()).id
  }

  async function installQaKernel() {
    const directory = join(homedir(), 'Library', 'Application Support', '@autoflow', 'desktop', 'data', 'kernels')
    const candidates = (await readdir(directory, { withFileTypes: true }).catch(() => []))
      .filter(entry => entry.isDirectory() && /^chromium-\d+(?:\.\d+){3,4}$/.test(entry.name))
      .map(entry => join(directory, entry.name))
      .sort()
      .reverse()
    for (const candidate of candidates) {
      const source = await realpath(candidate).catch(() => undefined)
      if (!source || !(await lstat(source)).isDirectory()) continue
      if (!(await stat(kernelExecutablePath(source, process.platform)).catch(() => undefined))?.isFile()) continue
      const destination = join(workspace, 'data', 'kernels', basename(source))
      assert.ok(isOwnedPm7Workspace(destination, owner, marker))
      await cp(source, destination, { recursive: true, dereference: false, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
      return basename(source).slice('chromium-'.length)
    }
    throw new Error('未找到已安装的公开版 CloakBrowser 内核；PM7 不执行浏览器，但资源校验仍需要一个已安装内核夹具')
  }

  async function saveFields(runtime, projectId, tableName, definitions) {
    await click('字段', '[role=tab]')
    for (const definition of definitions) {
      await click('新增字段')
      await input('#field-name', definition.name)
      await input('#field-key', definition.key)
      if (definition.required) await click('', '[aria-label="必填"]')
      await click('应用到草稿')
      await waitFor(renderer, "!document.querySelector('#schema-field-drawer-form')", 'field drawer closes')
    }
    await click('保存字段')
    await visible('保存字段前核对影响')
    await click('确认保存字段')
    await waitFor(renderer, "document.body.innerText.includes('暂无未保存修改')", 'field draft committed', 30_000)
    const table = (await api(runtime, `/projects/${projectId}/tables`)).items.find(item => item.name === tableName)
    assert.ok(table)
    const fields = (await api(runtime, `/projects/${projectId}/tables/${table.tableId}/fields`)).items
    assert.equal(fields.length, definitions.length)
    return { table, fields }
  }

  async function createRecord(runtime, projectId, table, fields, values, initialStatus) {
    await click('记录', '[role=tab]')
    const before = await api(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
    await click('', '[data-record-action="create"]')
    for (const [key, value] of Object.entries(values)) {
      const field = fields.find(item => item.key === key)
      assert.ok(field, `field ${key} must exist`)
      await doubleClick(`[data-record-draft] [data-grid-cell="0:${field.ref.fieldId}"]`)
      await input(`[data-record-draft] textarea[aria-label=${JSON.stringify(`第 1 行 · ${field.name}`)}]`, value)
    }
    await click('保存 1 行')
    await waitFor(renderer, `!document.querySelector('[aria-label="新增记录保存"]')`, 'inline record saved', 30_000)
    const page = await api(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
    assert.equal(page.total, before.total + 1, 'UI 保存必须只新增一条记录')
    const existingRefs = new Set(before.items.map(item => JSON.stringify(item.ref)))
    let created = page.items.find(item => !existingRefs.has(JSON.stringify(item.ref)))
    assert.ok(created, 'UI 保存后必须按稳定记录身份找回新增记录')
    if (initialStatus) {
      await click('', '[aria-label^="修改状态 "]')
      await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"记录业务状态\"]'))", 'record status editor')
      await click('', '[aria-label="记录业务状态"]')
      await click(initialStatus, '[role=option]')
      await wait(250)
      const targetStatus = (await api(runtime, `/projects/${projectId}/tables/${table.tableId}/statuses`)).items.find(item => item.name === initialStatus)
      assert.ok(targetStatus, `状态 ${initialStatus} 必须存在`)
      let statusPage = await api(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
      let persisted = statusPage.items.find(item => JSON.stringify(item.ref) === JSON.stringify(created.ref))
      if (persisted?.statusId !== targetStatus.statusId) {
        let submitted = false
        for (let attempt = 0; attempt < 100; attempt += 1) {
          statusPage = await api(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
          persisted = statusPage.items.find(item => JSON.stringify(item.ref) === JSON.stringify(created.ref))
          if (persisted?.statusId === targetStatus.statusId) break
          const canSubmit = await renderer.evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(item=>item.textContent.trim()==='保存状态');return Boolean(button&&!button.disabled)})()`)
          if (canSubmit && !submitted) {
            submitted = true
            await click('保存状态')
          }
          await wait(100)
        }
      }
      assert.equal(persisted?.statusId, targetStatus.statusId, `记录状态必须持久化为 ${initialStatus}`)
      await click('', '[aria-label="返回记录列表"]')
      const refreshed = await api(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
      created = refreshed.items.find(item => JSON.stringify(item.ref.recordKey) === JSON.stringify(created.ref.recordKey))
      assert.ok(created, '设置初始状态后必须找回同一条 UI 创建记录')
    }
    return created
  }

  async function createTable(runtime, projectId, name, fields, records = [], statuses = []) {
    await click('新建数据表')
    await input('#data-table-name', name)
    await input('#data-table-description', `${name}用于 PM7 三视图验收`)
    await click('创建数据表')
    await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"返回数据表\"]'))", 'table detail route')
    const schema = await saveFields(runtime, projectId, name, fields)
    if (statuses.length) {
      await click('状态', '[role=tab]')
      for (const status of statuses) {
        await click('新增状态')
        await input('#status-name', status)
        for (let attempt = 0; attempt < 3; attempt += 1) {
          await click('创建状态')
          const outcome = await waitFor(renderer, `(()=>!document.querySelector('#status-editor-form')?'closed':document.body.innerText.includes('载入最新资料')?'stale':null)()`, 'status save outcome', 30_000)
          if (outcome === 'closed') break
          await click('载入最新资料')
          await visible('用最新资料重新编辑？')
          await click('重新编辑')
          await waitFor(renderer, `!document.body.innerText.includes('数据已更新，请读取最新内容后重试')`, 'status editor refreshed', 30_000)
        }
      }
    }
    const created = []
    for (const record of records) created.push(await createRecord(runtime, projectId, schema.table, schema.fields, record.values, record.status))
    await click('返回数据表', '[aria-label="返回数据表"]')
    await visible(name)
    return { ...schema, records: created }
  }

  async function configureInput(alias, tableName, index) {
    await input('[aria-label^="输入别名 "]', alias, index)
    await waitFor(renderer, `!!document.querySelector('[aria-label=${JSON.stringify(`数据表 ${alias}`)}]')`, `${alias} input labels updated`)
    await click('', `[aria-label=${JSON.stringify(`数据表 ${alias}`)}]`)
    await click(tableName, '[role=option]')
    await click('', `[aria-label=${JSON.stringify(`必填输入 ${alias}`)}]`)
  }

  async function waitBatchTerminal(runtime, projectId, batchId) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const detail = await api(runtime, `/projects/${projectId}/batches/${batchId}`)
      if (['completed', 'failed', 'stopped', 'interrupted'].includes(detail.batch.status)) return detail
      await wait(200)
    }
    throw new Error(`batch ${batchId} did not reach terminal state`)
  }

  async function waitTaskCount(runtime, projectId, batchId, count) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const tasks = await api(runtime, `/projects/${projectId}/tasks?batchId=${batchId}&pageSize=100`)
      if (tasks.total === count && tasks.items.every(item => ['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'].includes(item.status))) return tasks
      await wait(200)
    }
    throw new Error(`batch ${batchId} did not expose ${count} terminal tasks`)
  }

  async function startBatch(runtime, projectId, count) {
    const startVisible = await renderer.evaluate(`[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='启动运行'&&!item.disabled&&item.getClientRects().length)`)
    if (!startVisible) {
      await click('自动化', '[aria-label="项目功能"] button')
      await visible('三表资料处理')
      await click('打开自动化 三表资料处理')
      await visible('启动运行')
    }
    await click('启动运行')
    await visible('启动自动化')
    await input('[aria-label="本次任务数"]', String(count))
    await visible('人员输入')
    await visible('邮箱输入')
    await click(`启动 ${count} 个任务`)
    await waitFor(renderer, `document.body.innerText.includes('本批次任务')||[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='核对原操作')`, 'batch page', 30_000)
    const batches = await api(runtime, `/projects/${projectId}/batches?pageSize=50`)
    const batch = batches.items.find(item => item.status === 'running' || item.status === 'queued') ?? batches.items.slice().sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0]
    assert.ok(batch, 'UI 启动后必须能按真实批次身份找回')
    return batch
  }

  async function openProjectTab(label) {
    await click(label, '[aria-label="项目功能"] button')
    if (label === '概览') await waitForSelector(renderer, '[aria-label="项目概览"]', '项目概览', 30_000)
    else await visible(label, 30_000)
  }

  // 从「运行记录 → 任务记录」打开一个真实终态为失败的任务详情。
  async function openFailedTaskDetail() {
    await openProjectTab('运行记录')
    await click('任务记录', '[role=tab]')
    await waitFor(renderer, `document.body.innerText.includes('任务记录')`, '任务记录页签')
    const row = await renderer.evaluate(`(()=>{const row=[...document.querySelectorAll('tbody tr')].find(item=>item.innerText.includes('失败'));if(!row)return null;const button=row.querySelector('button');if(!button)return null;button.scrollIntoView({block:'center'});button.click();return row.innerText})()`)
    assert.ok(row, '任务记录必须能按真实状态找到失败任务')
    await visible('输入与输出', 30_000)
    return row
  }

  try {
    const qaKernelVersion = await installQaKernel()
    let runtime = await launch()
    runtime.qaKernelVersion = qaKernelVersion
    await seedWorkflow(runtime, 'PM7 三表隔离执行器资料')
    await seedProfile(runtime)
    // Fixture setup happens after the desktop session is ready. Reload once so
    // resource queries cannot retain the pre-fixture empty catalog.
    await renderer.command('Page.reload', { ignoreCache: true })
    await visible('总览', 30_000)
    await click('项目')
    await visible('最近项目')
    if (options.prepareOnly) {
      await capture('00-isolated-ready', '00-projects/100-projects-prototype-5238b4.png')
      const result = await report('prepared', undefined, { preparation: '隔离工作区、PM7 QA sidecar、工作流与浏览器资源夹具已准备；未创建任何项目业务对象。' })
      console.log(JSON.stringify(result, null, 2))
      console.log('--prepare-only 只证明环境准备，不构成端到端通过。')
      return
    }

    await click('新建项目')
    await input('#project-name', 'PM7 三视图验收')
    await input('#project-description', '概览、统计、证据与失败后续的真实事实')
    await click('创建项目')
    await waitForProjectPage(renderer)
    const project = (await api(runtime, '/projects?q=PM7%20三视图验收')).items[0]
    assert.ok(project)
    checkpoint('UI 创建项目；只读 GET 找回同一真实项目。')
    await click('项目')
    await click('查看全部项目')
    await visible('PM7 三视图验收')
    await capture('00-projects-all', '00-projects/100-projects-prototype-5238b4.png')
    await click('PM7 三视图验收')
    await waitForProjectPage(renderer)

    await click('数据', '[aria-label="项目功能"] button')
    await visible('还没有数据表')
    const person = await createTable(runtime, project.projectId, '人员', [{ key: 'name', name: '姓名', required: true }], [{ values: { name: '张三' } }, { values: { name: '李四' } }])
    const email = await createTable(runtime, project.projectId, '邮箱', [{ key: 'email', name: '邮箱地址', required: true }], Array.from({ length: 6 }, (_, index) => ({ values: { email: `zhangsan+${index + 1}@example.test` } })), ['待使用', '已使用'])
    const account = await createTable(runtime, project.projectId, '账号', [
      { key: 'person', name: '人员', required: true },
      { key: 'email', name: '邮箱', required: true },
      { key: 'result', name: '网页结果', required: true },
    ])
    const personBefore = canonicalRecord(person.records[0])
    checkpoint('UI 创建三张表、必要字段、人员/邮箱记录与待使用/已使用状态；账号表为空。')

    await click('自动化', '[aria-label="项目功能"] button')
    await click('新建自动化')
    await input('[aria-label="自动化名称"]', '三表资料处理')
    await input('[aria-label="用途说明"]', '选择人员和邮箱，写入邮箱状态并新增账号')
    await click('关联工作流', '[role=combobox]')
    await click('PM7 三表隔离执行器资料', '[role=option]')
    await click('输入与参数', '[role=tab]')
    await click('添加数据输入')
    await click('添加数据输入')
    await configureInput('人员输入', '人员', 0)
    await configureInput('邮箱输入', '邮箱', 1)
    await clickNth('article summary', 3)
    await click('添加状态条件')
    await click('', '[aria-label="filter.items.0状态运算符"]')
    await click('为空', '[role=option]')
    await click('应用筛选')
    await click('资源与环境', '[role=tab]')
    await click('浏览器配置来源', '[role=combobox]')
    await click('指定浏览器配置', '[role=option]')
    await click('浏览器配置', '[role=combobox]')
    await click('PM7 隔离执行器资源', '[role=option]')
    await click('保存配置')
    await visible('自动化已创建', 30_000)
    checkpoint('UI 创建自动化并配置两个独立必填输入。')

    // ── E2E-1：成功 / 失败 / 停止三种真实终态 ───────────────────────────────
    await click('输入与参数', '[role=tab]')
    await waitFor(renderer, `(()=>{const values=[...document.querySelectorAll('input')].map(input=>input.value);return values.includes('人员输入')&&values.includes('邮箱输入')})()`, '两个必要输入卡片', 30_000)
    let batch = await startBatch(runtime, project.projectId, 3)
    let terminal = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
    assert.equal(terminal.batch.status, 'completed')
    let tasks = await waitTaskCount(runtime, project.projectId, batch.batchId, 3)
    assert.ok(tasks.items.every(item => item.status === 'succeeded'), '三个任务应全部成功')
    const succeededBatchId = batch.batchId
    checkpoint(`E2E-1 成功批次：UI 启动 3 个任务，全部 succeeded（批次 ${succeededBatchId}）。`)
    await visible('3 个任务', 30_000)
    await capture('03-runs-004-success-batch', '03-runs/004-batch-detail-approved-459f25.png')

    await fault(runtime, 'executor-fail')
    batch = await startBatch(runtime, project.projectId, 1)
    terminal = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
    tasks = await waitTaskCount(runtime, project.projectId, batch.batchId, 1)
    assert.equal(tasks.items[0].status, 'failed', '注入的失败必须真实落成 failed 终态')
    const failedTaskId = tasks.items[0].taskId
    const failedBatchId = batch.batchId
    await fault(runtime, 'executor-fail', { step: null })
    checkpoint(`E2E-1 失败批次：隔离执行器在 CREATE_ACCOUNT 注入失败，任务 ${failedTaskId} 落为 failed。`)

    await fault(runtime, 'executor-pause')
    batch = await startBatch(runtime, project.projectId, 1)
    const pauseBatchId = batch.batchId
    await wait(1500)
    await click('停止批次')
    await visible('停止当前批次？')
    await input('[aria-label="停止原因"]', 'PM7 E2E-1 停止与旧代次撤权验收')
    await capture('03-runs-015-stop-confirm', '03-runs/015-stop-confirm-e79f81.png')
    await click('确认停止')
    await visible('正在停止并核验资源清理', 30_000)
    await waitFor(renderer, `(()=>[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='强制停止'&&!item.disabled&&item.getClientRects().length))()`, '强制停止宽限期结束', 60_000)
    await click('强制停止')
    await visible('强制停止批次？')
    await input('[aria-label="确认强制停止"]', '强制停止')
    await input('[aria-label="停止原因"]', 'PM7 E2E-1 强制停止')
    await click('确认强制停止')
    // Force stop revokes the suspended worker; release it before waiting for terminal,
    // the same order production has (revoke, then the worker's late result is refused).
    await fault(runtime, 'executor-resume')
    terminal = await waitBatchTerminal(runtime, project.projectId, pauseBatchId)
    assert.equal(terminal.batch.status, 'stopped')
    let stoppedTasks = await api(runtime, `/projects/${project.projectId}/tasks?batchId=${pauseBatchId}&pageSize=100`)
    for (let attempt = 0; attempt < 100 && stoppedTasks.items.some(item => !['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'].includes(item.status)); attempt += 1) {
      await wait(200)
      stoppedTasks = await api(runtime, `/projects/${project.projectId}/tasks?batchId=${pauseBatchId}&pageSize=100`)
    }
    const cancelledCount = stoppedTasks.items.filter(item => item.status === 'cancelled').length
    checkpoint(`E2E-1 停止批次：UI 普通停止后强制停止，批次 stopped；其中 cancelled 任务 ${cancelledCount} 条。`)
    await capture('03-runs-010-batch-stopped', '03-runs/004-batch-detail-approved-459f25.png')

    // ── E2E-2：概览真实聚合 ───────────────────────────────────────────────
    const overview = await api(runtime, `/projects/${project.projectId}/overview?timezone=${encodeURIComponent('Asia/Shanghai')}`)
    assert.equal(overview.availability.statistics, 'available', '统计能力必须声明为 available')
    assert.equal(overview.counts.tables, 3)
    assert.equal(overview.counts.automations, 1)
    await openProjectTab('概览')
    const readCounts = `Object.fromEntries([...document.querySelectorAll('[aria-label="项目计数"] > div')].map(item=>[item.querySelector('dt')?.textContent?.trim()??'', item.querySelector('dd')?.textContent?.trim()??'']))`
    await waitFor(renderer, `(()=>{const counts=${readCounts};return counts['数据表']===${JSON.stringify(String(overview.counts.tables))}&&counts['自动化']===${JSON.stringify(String(overview.counts.automations))}})()`, `项目计数显示真实聚合（数据表 ${overview.counts.tables}、自动化 ${overview.counts.automations}）`, 30_000)
    const countsText = await renderer.evaluate(`document.querySelector('[aria-label="项目计数"]')?.innerText ?? ''`)
    assert.ok(countsText.includes('今日数据变化'), '概览必须有今日数据变化')
    await waitFor(renderer, `Boolean(document.querySelector('[aria-label="项目活动"]'))`, '项目活动分区')
    const sections = await renderer.evaluate(`[...document.querySelectorAll('[aria-label]')].map(e=>e.getAttribute('aria-label')).filter(Boolean)`)
    assert.ok(sections.includes('需要关注'), '概览必须有需要关注分区')
    assert.ok(sections.includes('继续工作'), '概览必须有继续工作分区')
    assert.ok(overview.recent.length > 0, '跑过批次后最近活动不能为空')
    await capture('01-overview-001', '01-overview/001')
    checkpoint(`E2E-1 概览事实：表 ${overview.counts.tables}、自动化 ${overview.counts.automations}、今日新增 ${overview.dataChanges?.newRecords ?? 0} / 更新 ${overview.dataChanges?.updatedRecords ?? 0}，活动 ${overview.activity.length} 条、最近 ${overview.recent.length} 条。`)

    // ── E2E-2：统计四指标与冻结集合下钻 ──────────────────────────────────
    await openProjectTab('统计')
    await waitForSelector(renderer, '[aria-label="统计指标"]', '统计指标', 30_000)
    const timezone = 'Asia/Shanghai'
    const to = new Date()
    const from = new Date(to.getTime() - 7 * 86_400_000)
    const statistics = await api(runtime, `/projects/${project.projectId}/statistics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&timezone=${encodeURIComponent(timezone)}&interval=day`)
    const allTasks = await api(runtime, `/projects/${project.projectId}/tasks?pageSize=100`)
    const terminalTasks = allTasks.items.filter(item => ['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'].includes(item.status))
    const sampleTotal = statistics.sample.succeeded + statistics.sample.failed + statistics.sample.cancelled + statistics.sample.timed_out + statistics.sample.interrupted
    assert.equal(sampleTotal, terminalTasks.length, '统计样本必须等于同一窗口内真实终态任务数')
    assert.equal(statistics.sample.succeeded, 3)
    assert.equal(statistics.sample.failed, 1)
    const denominator = statistics.sample.succeeded + statistics.sample.failed
    if (denominator > 0) {
      assert.ok(Math.abs(statistics.successRate - statistics.sample.succeeded / denominator) < 1e-9, '成功率必须是 成功/(成功+失败)')
    }
    const metricsText = await renderer.evaluate(`document.querySelector('[aria-label="统计指标"]')?.innerText ?? ''`)
    assert.ok(metricsText.includes('本期已结束任务'), '统计必须显示本期已结束任务')
    assert.ok(metricsText.includes('任务成功率'), '统计必须显示任务成功率')
    assert.ok(metricsText.includes('平均任务耗时'), '统计必须显示平均任务耗时')
    const noteText = await renderer.evaluate(`document.body.innerText`)
    assert.ok(noteText.includes('资源使用'), '统计页必须保留资源使用行')
    assert.ok(noteText.includes('尚未采集'), '统计页必须标注尚未采集')
    assert.ok(/成功率 = 成功/.test(noteText), '统计页必须有口径脚注')
    await capture('04-statistics-001', '04-statistics/001')
    if (statistics.failuresByAutomation.length > 0) {
      assert.equal(statistics.failuresByAutomation.reduce((sum, item) => sum + item.count, 0), statistics.sample.failed, '失败去向计数必须与失败任务数一致')
      await capture('04-statistics-006-failure-destinations', undefined)
    }

    const drilled = await renderer.evaluate(`(()=>{const button=[...document.querySelectorAll('[aria-label="统计指标"] button')].find(item=>item.textContent.trim()==='${statistics.sample.failed}');if(!button)return false;button.scrollIntoView({block:'center'});button.click();return true})()`)
    assert.ok(drilled, '统计的失败任务数必须是可点击的下钻入口')
    await visible('来自统计 · 失败任务', 30_000)
    const drillTasks = await api(runtime, `/projects/${project.projectId}/statistics/${encodeURIComponent(statistics.resultSetId)}/tasks?result=failed&page=1&pageSize=50`)
    assert.equal(drillTasks.total, statistics.sample.failed, '下钻集合必须与统计样本内的失败数一致')
    const drillText = await renderer.evaluate(`document.querySelector('[aria-label="失败任务记录"]')?.innerText ?? ''`)
    assert.ok(drillText.includes(String(drillTasks.total)), '下钻面板必须显示冻结集合条数')
    await capture('04-statistics-002-drill-down', '04-statistics/007-frozen-drilldown-00b0db.png')
    await click('返回统计')
    await waitForSelector(renderer, '[aria-label="统计指标"]', '统计指标')
    checkpoint(`E2E-2 统计：已结束 ${sampleTotal}（成功 ${statistics.sample.succeeded} / 失败 ${statistics.sample.failed} / 取消 ${statistics.sample.cancelled}），成功率 ${statistics.successRate ?? '无样本'}，下钻冻结集合 ${drillTasks.total} 条。`)

    const frozenDrill = await api(runtime, `/projects/${project.projectId}/statistics/${encodeURIComponent(statistics.resultSetId)}/tasks?result=failed&page=1&pageSize=50`)

    // ── E2E-4 任务证据 + E2E-3 失败后续 ───────────────────────────────────
    await openFailedTaskDetail()
    await capture('03-runs-002-task-detail', '03-runs/002')
    await click('输入与输出', '[role=tab]')
    await visible('原始数据输入')
    await visible('项目数据操作')
    const ioText = await renderer.evaluate('document.body.innerText')
    assert.ok(ioText.includes('人员输入') && ioText.includes('邮箱输入'), '任务详情必须显示两条不可变原始输入')
    const currentPanel = await renderer.evaluate(`document.querySelector('[aria-label="当前值对照"]')?.innerText ?? ''`)
    assert.ok(currentPanel.includes('快照值') && currentPanel.includes('当前值'), '输入与输出必须显示当前值对照')
    await capture('03-runs-003-task-input-output', '03-runs/006-task-input-output-approved-7af0aa.png')
    await click('异常与证据', '[role=tab]')
    await visible('失败时页面截图', 30_000)
    const evidenceText = await renderer.evaluate('document.body.innerText')
    assert.ok(evidenceText.includes('运行失败'), '证据页必须显示失败摘要')
    assert.ok(evidenceText.includes('历史尝试'), '证据页必须显示历史尝试')
    await capture('03-runs-003b-task-evidence', '03-runs/007-task-exception-evidence-approved-559ddf.png')
    checkpoint('E2E-4 任务证据：原始输入、项目数据操作、当前值对照与失败证据均在真实页面渲染。')

    await fault(runtime, 'followup-conflict', { projectId: project.projectId, taskId: failedTaskId })
    await click('以此输入重新运行')
    await visible('从原输入组重新运行？')
    await click('确认重新运行')
    await waitFor(renderer, `document.body.innerText.includes('从原输入组重新运行？')&&!document.body.innerText.includes('结果尚未确认')`, '冲突提示', 30_000)
    const conflictText = await renderer.evaluate(`document.querySelector('[role="dialog"]')?.innerText ?? document.body.innerText`)
    assert.ok(/刷新|重试|已更新/.test(conflictText), `修订冲突必须提示刷新重试，实际 ${JSON.stringify(conflictText.slice(0, 200))}`)
    await capture('03-runs-005-followup-conflict', '03-runs/004')
    checkpoint('E2E-5 修订冲突：源任务状态修订在提交前被推进，后续批次被真实拒绝且表单保留。')
    await pressKey('Escape')
    await wait(300)
    const conflictBatches = await api(runtime, `/projects/${project.projectId}/batches?pageSize=50`)
    assert.equal(conflictBatches.total, 3, '修订冲突不得产生任何新批次')

    // 冲突后按提示刷新，拿到推进后的真实修订再重试。
    await renderer.command('Page.reload', { ignoreCache: true })
    await visible('输入与输出', 30_000)

    const followupBefore = (await api(runtime, `/projects/${project.projectId}/batches?pageSize=50`)).total
    await fault(runtime, 'response-loss')
    await click('以此输入重新运行')
    await visible('从原输入组重新运行？')
    await click('确认重新运行')
    await visible('结果尚未确认', 30_000)
    await capture('03-runs-004-followup-uncertain', '03-runs/004')
    await click('核对原操作')
    await visible('后续批次已创建', 30_000)
    const followupAfter = await api(runtime, `/projects/${project.projectId}/batches?pageSize=50`)
    assert.equal(followupAfter.total, followupBefore + 1, '响应丢失后按原操作身份核验必须恰好产生一个批次')
    const recoveredDrill = await api(runtime, `/projects/${project.projectId}/statistics/${encodeURIComponent(statistics.resultSetId)}/tasks?result=failed&page=1&pageSize=50`)
    assert.equal(recoveredDrill.total, frozenDrill.total, '新批次产生后旧结果集的下钻集合必须保持不变')
    checkpoint(`E2E-3/E2E-5 失败后续：提交后响应丢失且核验查询也失败，用户按原操作身份核对找回，批次总数 ${followupAfter.total}；旧结果集下钻仍为 ${recoveredDrill.total} 条。`)

    // ── E2E-5：统计结果集过期与统计刷新失败 ───────────────────────────────
    // 结果集 TTL 到期：下钻必须被拒绝并给出刷新动作，不能悄悄换一组实时数据。
    await fault(runtime, 'statistics-ttl')
    await openProjectTab('统计')
    await waitForSelector(renderer, '[aria-label="统计指标"]', '统计指标', 30_000)
    const expiredDrill = await renderer.evaluate(`(()=>{const button=[...document.querySelectorAll('[aria-label="统计指标"] button')].find(item=>item.textContent.trim()==='${statistics.sample.failed}');if(!button)return false;button.scrollIntoView({block:'center'});button.click();return true})()`)
    assert.ok(expiredDrill, '统计的失败任务数必须可下钻，才能验证过期结果集')
    await visible('统计结果已过期', 30_000)
    checkpoint('E2E-5 统计结果集过期：TTL 到期后下钻被拒绝，页面提示“统计结果已过期，请刷新后重试”。')

    // 刷新失败：保留上次范围与数值，并明确标出这是上次结果。
    await fault(runtime, 'statistics-read-failure')
    await openProjectTab('运行记录')
    await openProjectTab('统计')
    await visible('统计刷新失败', 30_000)
    const retainedMetrics = await renderer.evaluate(`document.querySelector('[aria-label="统计指标"]')?.innerText ?? ''`)
    assert.ok(retainedMetrics.includes('本期已结束任务'), `统计刷新失败必须保留上次数据，实际 ${JSON.stringify(retainedMetrics.slice(0, 160))}`)
    const statisticsBanner = await renderer.evaluate(`[...document.querySelectorAll('[role="status"]')].map(item=>item.innerText).join(' | ')`)
    assert.ok(/以下是.*的结果/.test(statisticsBanner), `统计刷新失败必须标明沿用上次结果，实际 ${JSON.stringify(statisticsBanner)}`)
    await capture('04-statistics-006-refresh-failure', '04-statistics/006-statistics-error-2a8897.png')
    checkpoint('E2E-5 统计刷新失败：保留上次范围与数值并提示“统计刷新失败”。')

    // ── E2E-5：迟到事件 ──────────────────────────────────────────────────
    // 核对原操作后应用停在后续批次详情，先回到失败任务详情再注入迟到事件。
    await openFailedTaskDetail()
    const late = await fault(runtime, 'late-event', { taskId: failedTaskId })
    await wait(1200)
    const lateTask = await api(runtime, `/projects/${project.projectId}/tasks/${failedTaskId}`)
    assert.equal(lateTask.task.status, 'failed', '迟到事件不得改变任务终态')
    const lateEvents = await api(runtime, `/projects/${project.projectId}/tasks/${failedTaskId}/events?afterSequence=0`)
    assert.ok(lateEvents.items.some(item => item.sequence === late.sequence), '迟到事件必须能被真实补读')
    checkpoint(`E2E-5 迟到事件：注入 sequence ${late.sequence} 后任务仍为 failed，事件可按游标补读。`)

    // ── E2E-5：概览读取失败与迟到事件 ─────────────────────────────────────
    // The retained-values contract only applies once this page session has a
    // successful overview load; arm the fault after that and refetch on return.
    await openProjectTab('概览')
    await waitForSelector(renderer, '[aria-label="项目计数"]', '项目计数', 30_000)
    await openProjectTab('统计')
    await waitForSelector(renderer, '[aria-label="统计指标"]', '统计指标', 30_000)
    await fault(runtime, 'overview-read-failure')
    await openProjectTab('概览')
    await visible('概览刷新失败', 30_000)
    await capture('01-overview-008-refresh-failure', '01-overview/008')
    const retainedCounts = await renderer.evaluate(`document.querySelector('[aria-label="项目计数"]')?.innerText ?? ''`)
    assert.ok(retainedCounts.trim().length > 0, '概览读取失败必须保留上次数值卡片')
    assert.ok(retainedCounts.includes(String(overview.counts.tables)), `概览读取失败必须保留上次数值，实际 ${JSON.stringify(retainedCounts)}`)
    const failureBanner = await renderer.evaluate(`[...document.querySelectorAll('[role="status"]')].map(item=>item.innerText).join(' | ')`)
    assert.ok(/以下是上次加载的结果/.test(failureBanner), `有上次结果时失败提示必须说明沿用上次结果，实际 ${JSON.stringify(failureBanner)}`)
    checkpoint('E2E-5 概览读取失败：先成功取数再注入失败，页面保留上次数值并提示“概览刷新失败”。')

    // ── E2E-6：200% 缩放 ─────────────────────────────────────────────────
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 720, height: 512, deviceScaleFactor: 2, mobile: false })
    await capture('99-zoom-200', undefined)
    await openProjectTab('统计')
    await waitForSelector(renderer, '[aria-label="统计指标"]', '统计指标', 30_000)
    await capture('04-statistics-001-zoom200', '04-statistics/001')
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    checkpoint('E2E-6 边界：200% 缩放与长文本下没有横向撑宽。')

    const personKey = JSON.stringify(personBefore.ref)
    const personAfter = (await api(runtime, `/projects/${project.projectId}/tables/${person.table.tableId}/records?datasetGeneration=${encodeURIComponent(person.table.datasetGeneration)}&pageSize=100`)).items.find(item => JSON.stringify(item.ref) === personKey)
    assert.ok(personAfter, '人员记录必须仍然存在')
    assert.deepEqual(canonicalRecord(personAfter), personBefore, '人员记录必须完整保持不变')
    const statuses = (await api(runtime, `/projects/${project.projectId}/tables/${email.table.tableId}/statuses`)).items
    const usedStatusId = statuses.find(item => item.name === '已使用')?.statusId
    const emailsAfter = (await api(runtime, `/projects/${project.projectId}/tables/${email.table.tableId}/records?datasetGeneration=${encodeURIComponent(email.table.datasetGeneration)}&pageSize=100`)).items
    const accountsAfter = (await api(runtime, `/projects/${project.projectId}/tables/${account.table.tableId}/records?datasetGeneration=${encodeURIComponent(account.table.datasetGeneration)}&pageSize=100`)).items
    const finalTasks = await api(runtime, `/projects/${project.projectId}/tasks?pageSize=100`)
    const succeededTasks = finalTasks.items.filter(item => item.status === 'succeeded').length
    assert.equal(accountsAfter.length, succeededTasks, '每个成功任务只新增一个账号记录')
    assert.equal(new Set(accountsAfter.map(item => JSON.stringify(item.ref))).size, accountsAfter.length, '账号记录身份必须唯一')
    assert.ok(emailsAfter.filter(item => item.statusId === usedStatusId).length >= 4, '已执行任务必须把邮箱显式置为已使用')

    const facts = {
      projectId: project.projectId,
      succeededBatchId,
      failedBatchId,
      pauseBatchId,
      failedTaskId,
      samples: { overview: { counts: overview.counts, dataChanges: overview.dataChanges, activity: overview.activity.length, recent: overview.recent.length }, statistics: { sample: statistics.sample, successRate: statistics.successRate ?? null, averageDurationMs: statistics.averageDurationMs ?? null, failuresByAutomation: statistics.failuresByAutomation, resultSetId: statistics.resultSetId, drillTotal: drillTasks.total } },
      terminalTaskStatuses: Object.fromEntries(['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'].map(status => [status, finalTasks.items.filter(item => item.status === status).length])),
      personBefore, personAfter: canonicalRecord(personAfter),
      emailsUsed: emailsAfter.filter(item => item.statusId === usedStatusId).length,
      accountCount: accountsAfter.length,
      lateEventSequence: late.sequence,
      note: '多表输入与写入事实由隔离 QA 执行器产生；核心项目、表、字段、记录与自动化均通过界面创建。',
    }
    const result = await report('passed', undefined, facts)
    console.log(JSON.stringify({ status: result.status, scope: result.scope, runId, workspace, evidence, screenshots: screenshots.length, checkpoints: checkpoints.length }, null, 2))
    if (options.manual) {
      await applyManualInjections()
      console.log('应用保持打开。当前结果仅表示管理侧通过，真实执行核心接入待验收。按 Ctrl+C 退出。')
      await new Promise(() => {})
    }
  } catch (error) {
    if (renderer) {
      try { await capture('99-failure', undefined) } catch { /* preserve the original error */ }
    }
    const message = error instanceof Error ? error.stack ?? error.message : String(error)
    for (const entry of (await recordedNetwork()).slice(-6)) console.error(`  · HTTP ${entry.method} ${entry.status} ${entry.url} ${entry.body}`)
    const result = await report('failed', message)
    console.error(`PM7_QA_FAILURE ${join(evidence, 'report.json')}`)
    console.error(JSON.stringify({ status: result.status, error: message }, null, 2))
    throw error
  } finally {
    if (!options.manual) await shutdown()
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) await main()
