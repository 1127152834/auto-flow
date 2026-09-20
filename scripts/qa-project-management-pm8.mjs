#!/usr/bin/env node
/**
 * PM8 management-side acceptance harness.
 *
 * Runs real Electron + FastAPI + SQLite + the isolated QA executor
 * (`tests.qa.pm8_sidecar`, reachable only through the development QA switch) and
 * drives the lifecycle through the product's own renderer. Nothing here touches
 * Studio, and no production route is added for testing.
 *
 * Boundary: 管理侧通过，真实执行核心接入待验收。
 */
import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { chmod, cp, lstat, mkdir, mkdtemp, readdir, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage, waitForSelector } from './electron-cdp.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')

export const TERMINAL_TASK_STATUSES = ['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted']

export const PM8_FAULT_KINDS = Object.freeze([
  'expire-lifecycle-impact',
  'lifecycle-response-loss',
])

export const PM8_STEPS = Object.freeze([
  'E2E-1 界面创建项目、数据表、记录与自动化；启动一个真实任务',
  'E2E-2 活动任务阻断：设置页与归档影响都列出真实阻断项',
  'E2E-3 归档：影响预检 → 归档 → 写命令 409 → 只读导出可用',
  'E2E-4 恢复：历史任务状态与出站事实逐条不变',
  'E2E-5 永久删除：影响过期 412、确认名不符、删除后对象与本地文件消失',
  'E2E-6 资源保护：被项目引用的全局资源删除被拒并给出引用清单',
  'E2E-7 响应丢失：按原操作身份找回归档结果，不产生第二条事实',
  'E2E-8 清理残留：真实权限故障让删除停留在 deleting，重试清理后完成删除',
])

// 手测模式还需要执行器暂停/恢复/失败：PM8 sidecar 继承 PM7 的故障端点，
// 这些是稳定复现“活动批次阻断”和“失败任务”的唯一确定性手段。
export const PM8_MANUAL_FAULT_KINDS = Object.freeze(['executor-pause', 'executor-resume', 'executor-fail'])

export function parsePm8QaArgs(args) {
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
    if (!PM8_FAULT_KINDS.includes(kind) && !PM8_MANUAL_FAULT_KINDS.includes(kind) && kind !== 'service-restart') throw new Error(`unknown fault injection: ${kind}`)
  }
  return result
}

export function isOwnedPm8Workspace(path, ownerPath, marker) {
  const offset = relative(resolve(ownerPath), resolve(path))
  return marker?.kind === 'pm8-project-management-qa'
    && marker?.version === 1
    && offset !== '..'
    && !offset.startsWith(`..${sep}`)
    && !isAbsolute(offset)
}

export async function main(cliArgs = process.argv.slice(2)) {
  const options = parsePm8QaArgs(cliArgs)
  if (options.selfTest) {
    assert.equal(isOwnedPm8Workspace('/tmp/pm8-owner/workspace', '/tmp/pm8-owner', { kind: 'pm8-project-management-qa', version: 1 }), true)
    assert.equal(isOwnedPm8Workspace('/tmp/pm8-other/workspace', '/tmp/pm8-owner', { kind: 'pm8-project-management-qa', version: 1 }), false)
    assert.equal(isOwnedPm8Workspace('/tmp/pm8-owner/workspace', '/tmp/pm8-owner', { kind: 'pm7-project-management-qa', version: 1 }), false)
    assert.equal(PM8_STEPS.length, 8)
    assert.equal(PM8_FAULT_KINDS.length, 2)
    assert.deepEqual(
      parsePm8QaArgs(['--manual', '--inject=expire-lifecycle-impact']),
      { manual: true, prepareOnly: false, selfTest: false, cleanupOnly: false, workspace: undefined, inject: ['expire-lifecycle-impact'] },
    )
    assert.throws(() => parsePm8QaArgs(['--inject=nope']))
    console.log('PM8 QA helper self-test passed')
    return
  }

  if (options.cleanupOnly) {
    const target = options.workspace
    assert.ok(target, '--cleanup-only 需要 --workspace=<隔离工作区路径>')
    const ownerPath = resolve(target, '..')
    const marker = await readFile(join(ownerPath, '.pm8-qa.json'), 'utf8').then(JSON.parse, () => undefined)
    assert.ok(isOwnedPm8Workspace(target, ownerPath, marker), '只清理带 PM8 QA 所有权标记的目录')
    await rm(ownerPath, { recursive: true, force: true })
    console.log(`已清理 PM8 QA 隔离目录 ${ownerPath}`)
    return
  }

  const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
  const owner = await realpath(await mkdtemp(join(tmpdir(), `autoflow-pm8-qa-${runId}-`)))
  const workspace = options.workspace ? resolve(options.workspace) : join(owner, 'workspace')
  const marker = { kind: 'pm8-project-management-qa', version: 1, runId, createdAt: new Date().toISOString() }
  if (options.workspace) {
    assert.ok(await stat(workspace).then(() => true, () => false), '--workspace 必须已存在')
  } else {
    await mkdir(workspace)
    await writeFile(join(owner, '.pm8-qa.json'), JSON.stringify(marker, null, 2))
    await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
    await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))
  }

  const exportDir = join(owner, 'exports')
  await mkdir(exportDir, { recursive: true })
  const evidence = join(root, 'docs/project-management/implementation/pm8/qa-runs', runId)
  await mkdir(evidence, { recursive: true })
  const screenshots = []
  const checkpoints = []
  const boundary = { executor: 'isolatedQaExecutor', browser: 'notExecuted', studio: 'notExecuted' }
  const injections = []
  let desktop
  let renderer
  let native

  const checkpoint = message => { checkpoints.push(message); console.log(`✓ ${message}`) }
  // Progress markers exist so a stalled step is visible in the run log instead
  // of looking like a silent hang.
  const step = message => console.log(`· ${message}`)
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
      scenario: 'PM8-A management-side lifecycle, restart reconciliation and resource protection',
      scope: status === 'passed' ? '管理侧通过，真实执行核心接入待验收' : 'PM8 管理侧验收未通过',
      boundary,
      steps: PM8_STEPS,
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
      excluded: ['真实执行核心', 'Studio demo', '真实浏览器执行', 'Windows', '其他架构', '打包应用', '用户手动执行结果', '双工作区切换（见手测 M-08）'],
      createdAt: new Date().toISOString(),
    }
    await writeFile(join(evidence, 'report.json'), `${JSON.stringify(result, null, 2)}\n`)
    return result
  }

  // Every mutating request the renderer really sends is recorded, so a failure
  // carries the actual HTTP outcome instead of a re-derived guess.
  const installNetworkRecorder = () => renderer.evaluate(`(()=>{if(globalThis.__pm8Network)return true;globalThis.__pm8Network=[];const original=globalThis.fetch.bind(globalThis);globalThis.fetch=async(input,init)=>{const response=await original(input,init);try{const url=typeof input==='string'?input:(input?.url??'');const method=(init?.method??'GET').toUpperCase();if(String(url).includes('/api/v1/')&&(method!=='GET'||!response.ok)){let body='';try{body=(await response.clone().text()).slice(0,2000)}catch{}globalThis.__pm8Network.push({method,url:String(url),status:response.status,body})}}catch{}return response};return true})()`)
  const recordedNetwork = async () => (renderer ? await renderer.evaluate('globalThis.__pm8Network ?? []').catch(() => []) : [])
  const assertOwned = runtime => assert.ok(isOwnedPm8Workspace(runtime.workspaceKey, owner, marker), 'QA 只能修改带所有权标记的隔离工作区')

  async function launch() {
    const previous = {
      module: process.env.AUTOFLOW_QA_SIDECAR_MODULE,
      pm4: process.env.AUTOFLOW_PM4_QA,
      mode: process.env.AUTOFLOW_PM4_QA_MODE,
      maxAutoTasks: process.env.AUTOFLOW_PM4_QA_MAX_AUTO_TASKS,
      xlsxOutput: process.env.AUTOFLOW_QA_XLSX_OUTPUT,
    }
    process.env.AUTOFLOW_QA_SIDECAR_MODULE = 'tests.qa.pm8_sidecar'
    delete process.env.AUTOFLOW_PM4_QA
    process.env.AUTOFLOW_PM4_QA_MODE = 'f'
    process.env.AUTOFLOW_PM4_QA_MAX_AUTO_TASKS = '5'
    process.env.AUTOFLOW_QA_XLSX_OUTPUT = exportDir
    try {
      desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
    } finally {
      for (const [key, value] of Object.entries({ AUTOFLOW_QA_SIDECAR_MODULE: previous.module, AUTOFLOW_PM4_QA: previous.pm4, AUTOFLOW_PM4_QA_MODE: previous.mode, AUTOFLOW_PM4_QA_MAX_AUTO_TASKS: previous.maxAutoTasks, AUTOFLOW_QA_XLSX_OUTPUT: previous.xlsxOutput })) {
        if (value === undefined) delete process.env[key]
        else process.env[key] = value
      }
    }
    renderer = desktop.cdp
    native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate("globalThis.pm8Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm8Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await visible('本地服务正常', 30_000)
    const runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    await installNetworkRecorder()
    return runtime
  }

  // Quitting through the product's own IPC, then reaping the child, keeps a run
  // from parking an Electron instance in the QA workspace when the renderer is
  // unresponsive. The sockets are closed before the child so no command is sent
  // into a half-dead process.
  async function shutdown() {
    if (!desktop) return
    await renderer?.evaluate('window.autoflow.quitApplication?.()').catch(() => {})
    renderer?.close()
    native?.close()
    await stop(desktop.child).catch(() => {})
    desktop = undefined
    renderer = undefined
    native = undefined
  }

  async function visible(text, timeout = 15_000) {
    await waitFor(renderer, `(document.body?.innerText ?? '').includes(${JSON.stringify(text)})`, text, timeout)
  }

  // Real CDP pointer input, like the PM7 harness: Radix menus and tabs ignore
  // synthetic .click() because they listen for the pointer sequence.
  async function click(text, selector = 'button') {
    if (selector === '[role=tab]') text = ({ 记录: '数据记录', 字段: '字段与校验', 状态: '数据状态', 来源: '来源设置', 设置: '数据表设置' })[text] ?? text
    // Radix 浮层的入场动画会把元素从位移中拖回原位，先在移动鼠标后重新定位再按下，
    // 否则“坐标已过期”的点击会落在浮层外，把菜单关掉却什么都不选。
    const locate = () => waitFor(renderer, `(()=>{const visible=e=>{const s=getComputedStyle(e);return e.getClientRects().length&&!e.disabled&&s.display!=='none'&&s.visibility!=='hidden'&&s.pointerEvents!=='none'};const label=e=>{if(e.getAttribute('aria-label'))return e.getAttribute('aria-label');const copy=e.cloneNode(true);copy.querySelectorAll?.('[aria-hidden=true]').forEach(node=>node.remove());return copy.textContent.trim()};const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>visible(e)&&(${JSON.stringify(text)}===''||label(e)===${JSON.stringify(text)}));if(!items.length)return null;const hit=e=>{const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return x>=0&&x<=innerWidth&&y>=0&&y<=innerHeight&&e.contains(document.elementFromPoint(x,y))};const e=items.find(hit)??items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `${selector} ${text}`)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...(await locate()) })
    const point = await locate()
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(140)
  }

  async function clickNth(selector, index) {
    const point = await waitFor(renderer, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(item=>item.getClientRects().length&&!item.disabled)[${index}];if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `${selector}[${index}]`)
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

  const settle = () => new Promise(resolve => setTimeout(resolve, 1500))

  async function capture(name, reference) {
    await settle()
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate('({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})')
    assert.ok(geometry.scrollWidth <= geometry.viewport.width + 1, `${name} 不能撑宽应用`)
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    const bytes = Buffer.from(data, 'base64')
    const file = join(evidence, `${name}.png`)
    await writeFile(file, bytes)
    screenshots.push({ name, file, reference, ...geometry, sha256: createHash('sha256').update(bytes).digest('hex'), visualReview: 'pending' })
    console.log(`  · 截图 ${name} → ${reference ?? '（无对应画板）'}`)
  }

  async function api(runtime, path, init) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, {
      ...init,
      headers: { 'x-autoflow-token': runtime.sidecar.token, ...(init?.body ? { 'content-type': 'application/json' } : {}), ...init?.headers },
      signal: AbortSignal.timeout(20_000),
    })
    const body = await response.text()
    return { status: response.status, ok: response.ok, body: body ? JSON.parse(body) : undefined }
  }

  async function apiOk(runtime, path, init) {
    const response = await api(runtime, path, init)
    assert.ok(response.ok, `${init?.method ?? 'GET'} ${path}: ${response.status} ${JSON.stringify(response.body)}`)
    return response.body
  }

  async function fault(runtime, kind, body = {}) {
    assertOwned(runtime)
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1/qa/pm8/fault`, {
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

  async function restartService() {
    const previous = await renderer.evaluate('(async()=> (await window.autoflow.getRuntimeContext()).sidecar.instanceId)()')
    await renderer.evaluate('window.autoflow.restartSidecar()')
    await waitFor(renderer, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(previous)}})()`, 'service restarts', 30_000)
    await visible('本地服务正常', 30_000)
    checkpoint('测试服务完整重启并等待新实例 ready。')
  }

  async function applyManualInjections(runtime) {
    for (const kind of options.inject) {
      if (kind === 'service-restart') { await restartService(); continue }
      await fault(runtime, kind)
      console.log(`已注入 ${kind}（测试注入，记录在 report.json 的 injected 字段）。`)
    }
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
      assert.ok(isOwnedPm8Workspace(destination, owner, marker))
      await cp(source, destination, { recursive: true, dereference: false, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
      return basename(source).slice('chromium-'.length)
    }
    throw new Error('未找到已安装的公开版 CloakBrowser 内核；PM8 不执行浏览器，但资源校验仍需要一个已安装内核夹具')
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
    await waitFor(renderer, `(document.body?.innerText ?? '').includes('暂无未保存修改')`, 'field draft committed', 30_000)
    const tables = await apiOk(runtime, `/projects/${projectId}/tables`)
    const table = tables.items.find(item => item.name === tableName)
    assert.ok(table, `表 ${tableName} 必须已持久化`)
    const fields = (await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/fields`)).items
    assert.equal(fields.length, definitions.length, '字段数量必须与界面提交一致')
    return { table, fields }
  }

  async function createTable(runtime, projectId, name, fields, records = [], statuses = []) {
    await click('新建数据表')
    await input('#data-table-name', name)
    await input('#data-table-description', `${name}用于 PM8 生命周期验收`)
    await click('创建数据表')
    await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"返回数据表\"]'))", 'table detail route', 30_000)
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

  async function createRecord(runtime, projectId, table, fields, values, initialStatus) {
    await click('记录', '[role=tab]')
    const before = await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
    await click('', '[data-record-action="create"]')
    for (const [key, value] of Object.entries(values)) {
      const field = fields.find(item => item.key === key)
      assert.ok(field, `字段 ${key} 必须存在`)
      await doubleClick(`[data-record-draft] [data-grid-cell="0:${field.ref.fieldId}"]`)
      await input(`[data-record-draft] textarea[aria-label=${JSON.stringify(`第 1 行 · ${field.name}`)}]`, value)
    }
    await click('保存 1 行')
    await waitFor(renderer, "!document.querySelector('[aria-label=\"新增记录保存\"]')", 'inline record saved', 30_000)
    const page = await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
    assert.equal(page.total, before.total + 1, 'UI 保存必须只新增一条记录')
    const existing = new Set(before.items.map(item => JSON.stringify(item.ref)))
    let created = page.items.find(item => !existing.has(JSON.stringify(item.ref)))
    assert.ok(created, 'UI 保存后必须按稳定记录身份找回新增记录')
    if (initialStatus) {
      await click('', '[aria-label^="修改状态 "]')
      await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"记录业务状态\"]'))", 'record status editor')
      await click('', '[aria-label="记录业务状态"]')
      await click(initialStatus, '[role=option]')
      await wait(250)
      const target = (await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/statuses`)).items.find(item => item.name === initialStatus)
      assert.ok(target, `状态 ${initialStatus} 必须存在`)
      let submitted = false
      let persisted
      for (let attempt = 0; attempt < 100; attempt += 1) {
        const statusPage = await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)
        persisted = statusPage.items.find(item => JSON.stringify(item.ref) === JSON.stringify(created.ref))
        if (persisted?.statusId === target.statusId) break
        const canSubmit = await renderer.evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(item=>item.textContent.trim()==='保存状态');return Boolean(button&&!button.disabled)})()`)
        if (canSubmit && !submitted) { submitted = true; await click('保存状态') }
        await wait(100)
      }
      assert.equal(persisted?.statusId, target.statusId, `记录状态必须持久化为 ${initialStatus}`)
      await click('', '[aria-label="返回记录列表"]')
      created = (await apiOk(runtime, `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${encodeURIComponent(table.datasetGeneration)}`)).items.find(item => JSON.stringify(item.ref.recordKey) === JSON.stringify(created.ref.recordKey))
      assert.ok(created, '设置初始状态后必须找回同一条 UI 创建记录')
    }
    return created
  }

  async function configureInput(alias, tableName, index) {
    await input('[aria-label^="输入别名 "]', alias, index)
    await waitFor(renderer, `!!document.querySelector('[aria-label=${JSON.stringify(`数据表 ${alias}`)}]')`, `${alias} 输入标签`)
    await click('', `[aria-label=${JSON.stringify(`数据表 ${alias}`)}]`)
    await click(tableName, '[role=option]')
    await click('', `[aria-label=${JSON.stringify(`必填输入 ${alias}`)}]`)
  }

  async function startBatch(runtime, projectId, count, { automationName, inputs }) {
    const startVisible = await renderer.evaluate(`[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='启动运行'&&!item.disabled&&item.getClientRects().length)`)
    if (!startVisible) {
      await click('自动化', '[aria-label="项目功能"] button')
      await visible(automationName)
      await click(`打开自动化 ${automationName}`)
      await visible('启动运行')
    }
    await click('启动运行')
    await visible('启动自动化')
    await input('[aria-label="本次任务数"]', String(count))
    for (const alias of inputs) await visible(alias)
    await click(`启动 ${count} 个任务`)
    try {
      await waitFor(renderer, `(document.body?.innerText ?? '').includes('本批次任务')||[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='核对原操作')`, 'batch page', 30_000)
    } catch (error) {
      // The dialog is where the product reports a refused or uncertain command;
      // surfacing its text keeps a failure diagnosable without a second run.
      const dialog = await renderer.evaluate(`document.querySelector('[role=dialog]')?.innerText ?? ''`).catch(() => '')
      throw new Error(`${error.message}\n启动对话框：${String(dialog).replace(/\s+/g, ' ').slice(0, 1_500)}`)
    }
    const batches = await apiOk(runtime, `/projects/${projectId}/batches?pageSize=50`)
    const batch = batches.items.find(item => item.status === 'running' || item.status === 'queued')
      ?? batches.items.slice().sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0]
    assert.ok(batch, 'UI 启动后必须能按真实批次身份找回')
    return batch
  }

  async function waitBatchTasks(runtime, projectId, batchId, count) {
    let page
    for (let attempt = 0; attempt < 300; attempt += 1) {
      page = await apiOk(runtime, `/projects/${projectId}/tasks?batchId=${batchId}&pageSize=100`)
      if (page.total === count) return page
      await wait(200)
    }
    throw new Error(`批次 ${batchId} 未产生 ${count} 个任务（当前 ${page?.total ?? 0}）`)
  }

  async function waitTaskTerminal(runtime, projectId, batchId, count) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const page = await apiOk(runtime, `/projects/${projectId}/tasks?batchId=${batchId}&pageSize=100`)
      if (page.total === count && page.items.every(item => TERMINAL_TASK_STATUSES.includes(item.status))) return page
      await wait(200)
    }
    throw new Error(`批次 ${batchId} 的 ${count} 个任务未全部进入终态`)
  }

  async function waitBatchTerminal(runtime, projectId, batchId) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const detail = await apiOk(runtime, `/projects/${projectId}/batches/${batchId}`)
      if (['completed', 'failed', 'stopped', 'interrupted'].includes(detail.batch.status)) return detail
      await wait(200)
    }
    throw new Error(`批次 ${batchId} 未进入终态`)
  }

  async function waitProjectState(runtime, projectId, state) {
    let project
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const response = await api(runtime, `/projects/${projectId}`)
      if (response.status === 404) { assert.equal(state, 'deleted', `项目 ${projectId} 意外消失`); return undefined }
      project = response.body
      if (project?.lifecycleState === state) return project
      await wait(200)
    }
    throw new Error(`项目 ${projectId} 未收敛到 ${state}（当前 ${project?.lifecycleState}）`)
  }

  async function waitProjectGone(runtime, projectId) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const response = await api(runtime, `/projects/${projectId}`)
      if (response.status === 404) return true
      await wait(200)
    }
    throw new Error(`项目 ${projectId} 未删除`)
  }

  async function waitProjectRowsGone(runtime, projectId) {
    let rows
    for (let attempt = 0; attempt < 240; attempt += 1) {
      rows = await projectRowCount(runtime, projectId)
      // 删除成功后业务对象必须归零；项目行按契约保留为 deleted 墓碑（承载 workspace 幂等找回）。
      if (!rows.dataTables && (!rows.projects || rows.lifecycleState === 'deleted')) return rows
      await wait(500)
    }
    return rows
  }

  async function waitDeleteCleanupFailure(runtime, projectId, residuePath) {
    let seen
    for (let attempt = 0; attempt < 150; attempt += 1) {
      const page = await apiOk(runtime, `/projects/${projectId}/operations`)
      const failed = page.items.find(item => item.kind === 'deleteProject' && item.status === 'failed')
      if (failed) {
        assert.equal(failed.error?.code, 'DELETE_CLEANUP_FAILED', '清理失败必须留下明确的失败码')
        assert.equal(failed.error?.details?.retryable, true, '清理失败必须标记为可重试')
        const residue = failed.error?.details?.cleanup?.residue ?? []
        assert.ok(residue.includes(residuePath), `残留清单必须点名真实路径 ${residuePath}，实际 ${JSON.stringify(residue)}`)
        return failed
      }
      seen = page.items.filter(item => item.kind === 'deleteProject').map(item => item.status).join('、') || '（无删除操作）'
      await wait(200)
    }
    throw new Error(`删除清理未在 30s 内因真实权限故障失败并报告残留（deleteProject 状态：${seen}）`)
  }

  async function waitForExportFile() {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const names = (await readdir(exportDir).catch(() => [])).filter(name => name.endsWith('.xlsx'))
      if (names.length) {
        const info = await stat(join(exportDir, names[0]))
        if (info.size > 0) return { file: join(exportDir, names[0]), name: names[0], size: info.size }
      }
      await wait(200)
    }
    throw new Error('只读导出未在受控输出目录生成 xlsx')
  }

  async function faultPm7(runtime, kind, body = {}) {
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

  async function projectRowCount(runtime, projectId) {
    const code = `import sqlite3, sys
from pathlib import Path
connection = sqlite3.connect(str(Path(sys.argv[1]) / 'data' / 'autoflow.sqlite3'))
counts = {table: connection.execute(f'select count(*) from {table} where {"id" if table == "projects" else "project_id"}=?', (sys.argv[2],)).fetchone()[0] for table in ('projects', 'project_data_tables')}
state = connection.execute('select lifecycle_state from projects where id=?', (sys.argv[2],)).fetchone()
print(counts['projects'], counts['project_data_tables'], state[0] if state else 'absent')
connection.close()`
    const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, runtime.workspaceKey, projectId], { cwd: root })
    const [projects, tables, lifecycleState] = stdout.trim().split(/\s+/)
    return { projects: Number(projects), dataTables: Number(tables), lifecycleState }
  }

  async function openLifecycleDialog(projectName, label) {
    await click('', `[aria-label=${JSON.stringify(`更多${projectName}操作`)}]`)
    await waitFor(renderer, `Boolean(document.querySelector('[role=menuitem]'))`, 'project menu opens')
    await click(label, '[role=menuitem]')
    if (label === '恢复项目') {
      // 恢复没有确认对话框：菜单项点击后直接提交，结果以通知形式返回。
      await waitFor(renderer, `/项目已恢复|恢复命令已接受/.test(document.body?.innerText??'')`, '恢复结果提示', 30_000)
      return
    }
    await visible(label === '归档项目' ? '归档后项目变为只读' : '此操作无法撤销')
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
    const response = await apiOk(runtime, '/profiles', {
      method: 'POST',
      body: JSON.stringify({ name: 'PM8 隔离执行器资源', description: '仅作为管理端资源夹具', startUrl: 'about:blank', locale: null, timezone: null, geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: null, extensionPathsJson: [], expertArgsJson: [], browserVersion: runtime.qaKernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null }),
    })
    return response.id
  }

  try {
    step('复制公开版 CloakBrowser 内核夹具')
    const qaKernelVersion = await installQaKernel()
    step('启动隔离 Electron + PM8 QA sidecar')
    let runtime = await launch()
    runtime.qaKernelVersion = qaKernelVersion
    step('写入工作流与浏览器资源夹具')
    await seedWorkflow(runtime, 'PM8 生命周期隔离执行器资料')
    const profileId = await seedProfile(runtime)
    step('重载渲染层并进入项目目录')
    await renderer.command('Page.reload', { ignoreCache: true })
    await visible('总览', 30_000)
    // A reload replaces the execution context, so the recorder installed during
    // launch is gone by now. Without this the run loses every HTTP fact the
    // renderer really produced.
    await installNetworkRecorder()
    await click('项目')
    await visible('最近项目')
    step('环境就绪')
    if (options.prepareOnly) {
      await capture('00-isolated-ready', '00-projects/100-projects-prototype-5238b4.png')
      const result = await report('prepared', undefined, { preparation: '隔离工作区、PM8 QA sidecar、工作流与浏览器资源夹具已准备；未创建任何项目业务对象。' })
      console.log(JSON.stringify(result, null, 2))
      console.log('--prepare-only 只证明环境准备，不构成端到端通过。')
      return
    }
    if (options.manual) {
      console.log(`隔离环境已就绪：${workspace}`)
      console.log('按 docs/project-management/implementation/pm8/manual-test.md 逐步操作；完成后回到本终端按 Ctrl+C。')
      await new Promise(() => {})
    }
    const projectName = 'PM8 生命周期验收'
    const keepName = 'PM8 保留项目'
    const automationName = 'PM8 生命周期自动化'
    const workflowName = 'PM8 生命周期隔离执行器资料'
    const profileName = 'PM8 隔离执行器资源'
    const visibleDirectory = () => waitFor(renderer, `Boolean(document.querySelector('[aria-label="项目目录"]'))`, '项目目录', 30_000)
    const cardPresent = name => `Boolean([...document.querySelectorAll('article')].find(card=>card.innerText.includes(${JSON.stringify(name)})))`
    const openFromDirectory = async name => { await click(name); await waitForProjectPage(renderer) }
    // 目录的两种视图与状态筛选都是真实产品规则：新建但从未打开的项目不进“最近项目”，
    // 归档项目在不含“已归档”的状态筛选下也不出现在“全部项目”。这里按真实操作把卡片找出来，
    // 而不是放宽断言或改用 API 跳转绕过页面。
    const ensureProjectCard = async (name, lifecycle = 'active') => {
      if (await renderer.evaluate(cardPresent(name))) return
      if (await renderer.evaluate(`Boolean([...document.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')==='查看全部项目'))`)) await click('查看全部项目')
      await waitFor(renderer, `Boolean(document.querySelector('[aria-label="项目状态"]'))`, '全部项目视图', 30_000)
      if (!await renderer.evaluate(cardPresent(name))) {
        await click('', '[aria-label="项目状态"]')
        await click({ active: '活动项目', archived: '已归档', all: '全部状态' }[lifecycle], '[role=option]')
        await wait(300)
      }
      await waitFor(renderer, cardPresent(name), `${name} 项目卡片`, 30_000)
    }
    // 目录是目的地，“返回项目目录”只是从项目页过去的一条路径：已在目录时不再点不存在的按钮。
    const backToDirectory = async (lifecycle = 'active') => {
      if (!(await renderer.evaluate('Boolean(document.querySelector(\'[aria-label="项目目录"]\'))'))) await click('返回项目目录')
      await visibleDirectory()
      await ensureProjectCard(projectName, lifecycle)
    }
    // 命令接受后生命周期对话框停留在进度视图，关闭它只表示离开视图，命令本身继续收敛。
    const dismissLifecycleProgress = async () => {
      await waitFor(renderer, `!document.querySelector('[role=dialog]')||(document.body?.innerText??'').includes('命令已接受')`, '生命周期进度视图', 30_000)
      if (await renderer.evaluate(`Boolean(document.querySelector('[role=dialog]'))`)) await click('取消')
      await waitFor(renderer, `!document.querySelector('[role=dialog]')`, '生命周期进度视图关闭', 30_000)
    }

    // ── E2E-1：界面创建项目、数据表、记录、自动化并启动一个真实任务 ────────
    step('E2E-1 界面创建项目、三张表、记录与自动化')
    await click('新建项目')
    await input('#project-name', projectName)
    await input('#project-description', 'PM8 生命周期：归档、只读导出、恢复与永久删除')
    await click('创建项目')
    await waitForProjectPage(renderer)
    const project = (await apiOk(runtime, `/projects?q=${encodeURIComponent(projectName)}`)).items.find(item => item.name === projectName)
    assert.ok(project, 'UI 创建后必须能按真实身份找回项目')
    checkpoint('界面创建项目；只读 GET 找回同一真实项目。')

    await click('数据', '[aria-label="项目功能"] button')
    await visible('还没有数据表')
    await createTable(runtime, project.projectId, '人员', [{ key: 'name', name: '姓名', required: true }], [{ values: { name: '张三' } }])
    await createTable(runtime, project.projectId, '邮箱', [{ key: 'email', name: '邮箱地址', required: true }], [{ values: { email: 'zhangsan+1@example.test' } }], ['待使用', '已使用'])
    await createTable(runtime, project.projectId, '账号', [
      { key: 'person', name: '人员', required: true },
      { key: 'email', name: '邮箱', required: true },
      { key: 'result', name: '网页结果', required: true },
    ])
    checkpoint('界面创建三张表、必要字段、一条人员记录与一条未设置业务状态的邮箱；邮箱表带待使用/已使用两个状态；账号表为空。')

    await click('自动化', '[aria-label="项目功能"] button')
    await click('新建自动化')
    await input('[aria-label="自动化名称"]', automationName)
    await input('[aria-label="用途说明"]', 'PM8 生命周期验收：真实任务阻断、归档、只读导出与恢复')
    await click('关联工作流', '[role=combobox]')
    await click(workflowName, '[role=option]')
    await click('输入与参数', '[role=tab]')
    await click('添加数据输入')
    await click('添加数据输入')
    await configureInput('人员输入', '人员', 0)
    await configureInput('邮箱输入', '邮箱', 1)
    await clickNth('article summary', 3)
    await click('添加状态条件')
    await click('', '[aria-label="filter.items.0状态运算符"]')
    // 邮箱按业务状态选取：只领取尚未使用的邮箱，运行后由工作流改为“已使用”。
    await click('为空', '[role=option]')
    await waitFor(renderer, `(()=>{const t=document.querySelector('[aria-label="filter.items.0状态运算符"]');return t&&t.innerText.includes('为空')?true:null})()`, '状态运算符切到为空', 10_000)
    await click('应用筛选')
    await click('资源与环境', '[role=tab]')
    await click('浏览器配置来源', '[role=combobox]')
    await click('指定浏览器配置', '[role=option]')
    await click('浏览器配置', '[role=combobox]')
    await click(profileName, '[role=option]')
    await click('保存配置')
    await visible('自动化已创建', 30_000)
    const automation = (await apiOk(runtime, `/projects/${project.projectId}/automations`)).items.find(item => item.name === automationName)
    assert.ok(automation, '界面保存后必须能按真实身份找回自动化')
    checkpoint('界面创建自动化，绑定一个真实数据输入与浏览器资源。')

    await faultPm7(runtime, 'executor-pause')
    await click('输入与参数', '[role=tab]')
    const batch = await startBatch(runtime, project.projectId, 1, { automationName, inputs: ['人员输入', '邮箱输入'] })
    const paused = await waitBatchTasks(runtime, project.projectId, batch.batchId, 1)
    assert.equal(paused.items[0].status, 'running', '暂停注入必须让任务保持运行中')
    checkpoint(`E2E-1 界面启动 1 个真实任务并保持运行：批次 ${batch.batchId}、任务 ${paused.items[0].taskId}。`)
    await capture('01-runs-batch-running', '03-runs/004-batch-detail-approved-459f25.png')

    // ── E2E-2：活动任务阻断设置页退出与归档 ──────────────────────────────
    step('E2E-2 活动任务阻断')
    const blockedImpact = await apiOk(runtime, `/projects/${project.projectId}/lifecycle-impact?action=archive`)
    assert.ok(blockedImpact.blockers.some(item => item.code === 'BATCH_ACTIVE' || item.code === 'TASK_ACTIVE'), '归档影响必须列出活动批次/任务阻断')
    await click('设置')
    await click('工作区', '[role=tab]')
    const blockedText = await waitFor(renderer, `(()=>{const text=document.body.innerText;return text.includes('无法切换')?text:null})()`, '工作区阻断提示', 30_000)
    assert.ok(blockedText.includes('项目批次正在运行'), '设置页必须把 project_batches_active 译为可处理的中文阻断说明')
    assert.ok(!blockedText.includes('本地任务进行中，请等待任务结束'), '项目侧阻断不得退回泛化兜底文案')
    await capture('02-settings-blockers', undefined)
    checkpoint(`E2E-2 设置页退出/切换工作区阻断列出项目侧真实阻断：${blockedImpact.blockers.map(item => item.code).join('、')}。`)

    await click('项目')
    await visibleDirectory()
    await ensureProjectCard(projectName)
    await openLifecycleDialog(projectName, '归档项目')
    const blockedPanel = await waitFor(renderer, `(()=>{const section=document.querySelector('[aria-label="阻断项"]');return section?section.innerText:null})()`, '归档阻断项', 30_000)
    assert.ok(blockedPanel.includes('BATCH_ACTIVE') || blockedPanel.includes('批次尚未结束') || blockedPanel.includes('任务尚未结束'), '归档对话框必须展示真实阻断')
    await capture('03-archive-blocked', '05-data/015-delete-table-blocked-2b8a64.png')
    await click('取消')
    checkpoint('E2E-2 归档影响预检展示同一组真实阻断，且预检未改变任何状态。')

    await faultPm7(runtime, 'executor-resume')
    const batchTerminal = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
    const finished = await waitTaskTerminal(runtime, project.projectId, batch.batchId, 1)
    checkpoint(`E2E-2 恢复执行后批次 ${batchTerminal.batch.status}、任务 ${finished.items[0].status}，阻断随真实事实消失。`)

    // ── E2E-3：归档、写命令 409 与只读导出 ───────────────────────────────
    step('E2E-3 归档、拒绝写入与只读导出')
    const tasksBefore = await apiOk(runtime, `/projects/${project.projectId}/tasks?pageSize=100`)
    await backToDirectory()
    await openLifecycleDialog(projectName, '归档项目')
    await visible('归档影响')
    await capture('04-archive-confirm', '02-automation/004-delete-confirm-54c904.png')
    await click('归档项目')
    await dismissLifecycleProgress()
    const archived = await waitProjectState(runtime, project.projectId, 'archived')
    assert.equal(archived.lifecycleState, 'archived')
    checkpoint('E2E-3 归档命令被接受并在无 HTTP 请求维持下收敛为 archived。')

    const writeRejected = await api(runtime, `/projects/${project.projectId}/tables`, { method: 'POST', headers: { 'Idempotency-Key': randomUUID() }, body: JSON.stringify({ name: '归档后写入', description: '', sourceKind: 'local' }) })
    assert.equal(writeRejected.status, 409, `归档后写命令必须 409，实际 ${writeRejected.status}`)
    assert.equal(writeRejected.body.error?.code, 'LIFECYCLE_CONFLICT')
    const readStillWorks = await apiOk(runtime, `/projects/${project.projectId}/tables`)
    assert.ok(Array.isArray(readStillWorks.items) && readStillWorks.items.length === 3, '归档项目只读查询仍必须可用')
    checkpoint(`E2E-3 归档后写命令 409 LIFECYCLE_CONFLICT，只读查询仍返回 ${readStillWorks.items.length} 张表。`)

    await ensureProjectCard(projectName, 'archived')
    await openFromDirectory(projectName)
    await click('数据', '[aria-label="项目功能"] button')
    await click('打开数据表：人员')
    await click('记录', '[role=tab]')
    await capture('05-archived-readonly', '02-automation/010-archived-readonly-46a6a4.png')
    await click('', '[data-record-action="more"]')
    await click('导出 Excel', '[role=menuitem]')
    await visible('导出 Excel')
    await capture('06-export-dialog', undefined)
    await click('选择保存位置')
    const exported = await waitForExportFile()
    assert.ok(exported.size > 0, '只读导出必须产出非空 xlsx')
    const exportedInBytes = (await readFile(exported.file)).subarray(0, 2).toString('binary')
    assert.equal(exportedInBytes, 'PK', '导出结果必须是真实 xlsx 容器')
    checkpoint(`E2E-3 归档项目只读导出成功：${exported.name}（${exported.size} 字节）。`)
    await click('关闭')

    // ── E2E-4：恢复不重跑历史事实 ────────────────────────────────────────
    step('E2E-4 恢复后历史事实不变')
    await backToDirectory('archived')
    await openLifecycleDialog(projectName, '恢复项目')
    const restored = await waitProjectState(runtime, project.projectId, 'active')
    assert.equal(restored.lifecycleState, 'active')
    const tasksAfter = await apiOk(runtime, `/projects/${project.projectId}/tasks?pageSize=100`)
    const shape = item => [item.taskId, item.status, item.statusRevision, item.updatedAt, item.startedAt ?? null, item.completedAt ?? null]
    assert.deepEqual(tasksAfter.items.map(shape), tasksBefore.items.map(shape), '恢复不得重跑、重发或改写历史任务')
    const operations = await apiOk(runtime, `/projects/${project.projectId}/operations`)
    const archiveFacts = operations.items.filter(item => item.kind === 'archiveProject')
    const restoreFacts = operations.items.filter(item => item.kind === 'restoreProject')
    assert.equal(archiveFacts.length, 1, '归档只允许有一条事实')
    assert.equal(restoreFacts.length, 1, '恢复只允许有一条事实')
    const exportedAfterRestore = (await readdir(exportDir)).filter(name => name.endsWith('.xlsx')).length
    assert.equal(exportedAfterRestore, 1, '恢复不得重放导出')
    checkpoint(`E2E-4 恢复后 ${tasksAfter.total} 条历史任务事实逐字不变，归档/恢复各一条操作记录，导出未被重放。`)

    // ── E2E-6：全局资源引用保护（在删除项目之前核对） ────────────────────
    step('E2E-6 全局资源引用保护')
    const profileBlocked = await api(runtime, `/profiles/${profileId}`, { method: 'DELETE' })
    assert.equal(profileBlocked.status, 409, `被引用的浏览器配置删除必须 409，实际 ${profileBlocked.status}`)
    const profileError = profileBlocked.body.error
    assert.equal(profileError?.code, 'RESOURCE_REFERENCED')
    const named = (profileError.details?.references ?? []).some(item => item.projectId === project.projectId && item.automationName === automationName)
    assert.ok(named, '引用清单必须指名项目与自动化')
    // 真实界面路径：全局导航 → 浏览器配置 → 对被引用的配置执行删除。
    await click('浏览器配置')
    await waitFor(renderer, `Boolean(document.querySelector(${JSON.stringify(`[aria-label="删除 ${profileName}"]`)}))`, '被引用配置的删除按钮', 30_000)
    await click(`删除 ${profileName}`)
    await visible('删除浏览器配置')
    await click('确认删除')
    const referencePanel = await waitFor(renderer, `(()=>{const node=[...document.querySelectorAll('[role=alert]')].find(item=>item.innerText.includes('仍被以下对象引用'));return node?node.innerText:null})()`, '引用清单', 30_000)
    assert.ok(referencePanel.includes(projectName), '界面引用清单必须指名项目')
    assert.ok(referencePanel.includes(automationName), '界面引用清单必须指名自动化')
    assert.ok(referencePanel.includes('请先在对应项目或自动化里改用别的资源'), '界面引用清单必须给出处理去向')
    // 点击删除按钮时的 scrollIntoView 会把文档滚过顶部导航；弹窗本身是 fixed，
    // 回到文档顶部才能拍到与原型同结构的全局导航。
    await renderer.evaluate('window.scrollTo(0, 0)')
    await capture('07-resource-referenced', '05-data/015-delete-table-blocked-2b8a64.png')
    await click('取消')
    await click('项目')
    checkpoint(`E2E-6 被引用的浏览器配置删除被拒：接口 409 与真实界面引用清单都命名 ${profileError.details.references.length} 条引用（项目 + 自动化）。`)

    // ── 保留项目：删除 A 之后仍必须完整 ─────────────────────────────────
    await click('新建项目')
    await input('#project-name', keepName)
    await input('#project-description', '永久删除 A 之后必须保留的项目与全局资源')
    await click('创建项目')
    await waitForProjectPage(renderer)
    const keep = (await apiOk(runtime, `/projects?q=${encodeURIComponent(keepName)}`)).items.find(item => item.name === keepName)
    assert.ok(keep, '保留项目必须按真实身份找回')
    await backToDirectory()

    // ── E2E-5：永久删除的影响过期、名称校验与真实删除 ───────────────────
    step('E2E-5 永久删除')
    // 永久删除只对已归档项目开放：先按产品规则重新归档，再验证删除影响。
    await openLifecycleDialog(projectName, '归档项目')
    await visible('归档影响')
    await click('归档项目')
    await dismissLifecycleProgress()
    const archivedAgain = await waitProjectState(runtime, project.projectId, 'archived')
    await visibleDirectory()
    await ensureProjectCard(projectName, 'archived')
    await openLifecycleDialog(projectName, '永久删除')
    await visible('此操作无法撤销')
    await fault(runtime, 'expire-lifecycle-impact', { projectId: project.projectId })
    await input('[aria-label="确认项目名称"]', projectName)
    await click('永久删除')
    await visible('影响范围可能已变化，请重新核对后再确认。', 30_000)
    const staleReject = await api(runtime, `/projects/${project.projectId}`, { method: 'DELETE', headers: { 'Idempotency-Key': randomUUID() }, body: JSON.stringify({ confirmationName: projectName, impactRevision: 1, expectedManagementRevision: archivedAgain.managementRevision }) })
    assert.equal(staleReject.status, 412, `过期影响必须 412，实际 ${staleReject.status}`)
    await capture('08-delete-stale-impact', '05-data/015-delete-table-blocked-2b8a64.png')
    checkpoint('E2E-5 影响确认过期后删除被拒 412，界面要求重新核对且未产生删除事实。')

    await click('重新核对影响')
    await visible('输入项目名称以确认', 30_000)
    await input('[aria-label="确认项目名称"]', '错误的项目名称')
    const nameGuarded = await renderer.evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(item=>item.textContent.trim()==='永久删除');return Boolean(button&&button.disabled)})()`)
    assert.ok(nameGuarded, '确认名不符时删除按钮必须禁用')
    const nameReject = await api(runtime, `/projects/${project.projectId}`, { method: 'DELETE', headers: { 'Idempotency-Key': randomUUID() }, body: JSON.stringify({ confirmationName: '错误的项目名称', impactRevision: blockedImpact.impactRevision, expectedManagementRevision: archivedAgain.managementRevision }) })
    assert.equal(nameReject.status, 422, `确认名不符必须 422，实际 ${nameReject.status}`)
    await capture('09-delete-name-guard', '02-automation/004-delete-confirm-54c904.png')
    checkpoint('E2E-5 确认名不符时界面禁用提交，直连接口同样拒绝 422。')

    // ── E2E-8：清理残留真实可见 + 重试清理 ─────────────────────────────
    // 残留必须来自产品在文件系统层的真实失败：把项目自己的隔离工作副本置为
    // 不可遍历，让本地清理真的删不掉它，而不是伪造一条失败事实。
    // 隔离执行器不启动浏览器，因此工作副本由侧车按真实环境仓库登记（测试注入）；
    // 删除、残留判定、重试收敛本身全部走产品路径。
    step('E2E-8 清理残留与重试清理')
    const leaked = await fault(runtime, 'leak-work-copy', { projectId: project.projectId, profileId })
    const instanceDir = leaked.directory
    assert.ok(await stat(instanceDir).then(() => true, () => false), `隔离工作副本必须真实存在：${instanceDir}`)
    const instancePage = await apiOk(runtime, `/projects/${project.projectId}/environment-instances`)
    assert.ok(instancePage.items.some(item => item.instanceId === leaked.instanceId), '遗留工作副本必须能按真实实例身份读回')
    await chmod(instanceDir, 0o000)
    injections.push(`cleanup-residue：将遗留工作副本 ${instanceDir} 置为 000 权限，令真实删除的本地清理失败（测试注入）`)

    await input('[aria-label="确认项目名称"]', projectName)
    await click('永久删除')
    await dismissLifecycleProgress()
    const residueOperation = await waitDeleteCleanupFailure(runtime, project.projectId, instanceDir)
    const stuck = await apiOk(runtime, `/projects/${project.projectId}`)
    assert.equal(stuck.lifecycleState, 'deleting', '清理失败后项目必须停留在 deleting')
    checkpoint(`E2E-8 真实权限故障让删除失败：操作 ${residueOperation.operationId} 报告 DELETE_CLEANUP_FAILED 与 ${residueOperation.error.details.cleanup.residue.length} 条残留，项目停留在 deleting。`)

    // 归档目录筛选同时承载 deleting 项目：刷新后卡片必须把残留与重试入口摆出来。
    await visibleDirectory()
    await click('', '[aria-label="刷新项目"]')
    await ensureProjectCard(projectName, 'archived')
    await waitFor(renderer, `(document.body?.innerText ?? '').includes('清理未完成')`, '清理未完成标记', 30_000)
    await capture('12-delete-cleanup-residue', '00-projects/100-projects-prototype-5238b4.png')
    await click('', `[aria-label=${JSON.stringify(`更多${projectName}操作`)}]`)
    await waitFor(renderer, `Boolean([...document.querySelectorAll('[role=menuitem]')].find(item=>item.textContent.trim()==='重试清理'))`, '重试清理入口', 30_000)
    await click('重试清理', '[role=menuitem]')
    // 重试对话框的残留清单来自 onLoadResidue 读到的真实操作证据，不是本地状态。
    await visible('本地文件未能完全清理', 30_000)
    await visible(instanceDir, 30_000)
    await capture('13-cleanup-residue-retry', '02-automation/004-delete-confirm-54c904.png')
    checkpoint('E2E-8 归档目录卡片显示「清理未完成」，重试入口与重试对话框的残留清单都点名真实路径。')

    await input('[aria-label="确认项目名称"]', projectName)
    await click('重试清理')
    await dismissLifecycleProgress()
    // 重试是新的删除命令（残留证据保留在先前那条失败事实上），不是换键重发旧命令。
    const deleteOperations = (await apiOk(runtime, `/projects/${project.projectId}/operations`)).items.filter(item => item.kind === 'deleteProject')
    assert.equal(deleteOperations.length, 2, `重试必须产生第二条删除命令，实际 ${deleteOperations.length} 条（${deleteOperations.map(item => item.status).join('、')}）`)
    assert.ok(deleteOperations.some(item => item.status === 'failed' && (item.error?.details?.cleanup?.residue ?? []).includes(instanceDir)), '先前失败事实与残留证据必须保留')

    // 故障注入解除后，收敛循环用同一条重试命令完成真实清理。
    await chmod(instanceDir, 0o755)
    injections.push(`cleanup-residue-cleared：将 ${instanceDir} 恢复为 755，允许真实重试清理（测试注入解除）`)
    await waitProjectGone(runtime, project.projectId)
    assert.ok(!(await stat(instanceDir).then(() => true, () => false)), '重试清理必须真的删掉残留目录')
    // 删除在后台收敛：行清理晚于只读视图消失，等待真实事实落地而不是立刻断言。
    const rows = await waitProjectRowsGone(runtime, project.projectId)
    // 契约（spec §2.1 deleted + test_project_lifecycle.py）要求：数据表/记录等业务对象全部删除，
    // 项目行保留为 lifecycle_state='deleted' 的墓碑，用于 workspace 作用域的幂等找回；对外读取必须 404。
    assert.equal(rows.dataTables, 0, '删除后 A 的数据表行必须归零')
    assert.equal(rows.projects, 1, '删除后必须保留 deleted 墓碑行以承载 workspace 幂等找回')
    assert.equal(rows.lifecycleState, 'deleted', '墓碑项目行必须处于 deleted 状态')
    const tombstoneRead = await api(runtime, `/projects/${project.projectId}`)
    assert.equal(tombstoneRead.status, 404, '墓碑项目对外读取必须 404')
    const keepAfter = await apiOk(runtime, `/projects/${keep.projectId}`)
    assert.equal(keepAfter.lifecycleState, 'active')
    const profileAfter = await apiOk(runtime, '/profiles')
    assert.ok(profileAfter.items.some(item => item.id === profileId), '删除项目不得连带删除全局资源')
    // 截图必须同时可核对“A 已消失、B 仍保留”，所以切到全部状态目录，而不是停在已归档的 0 条视图。
    await ensureProjectCard(keepName, 'all')
    await capture('10-deleted-project-kept-neighbour', '00-projects/100-projects-prototype-5238b4.png')
    checkpoint(`E2E-5 永久删除完成：A 的数据表行归零、项目行保留为 deleted 墓碑且对外读取 404，B 项目与全局浏览器配置保留。`)

    // ── E2E-7：响应丢失后按原操作身份找回 ────────────────────────────────
    step('E2E-7 响应丢失后按原操作身份找回')
    await ensureProjectCard(keepName, 'active')
    await fault(runtime, 'lifecycle-response-loss')
    await openLifecycleDialog(keepName, '归档项目')
    await visible('归档影响')
    await click('归档项目')
    await visible('上次保存结果尚未确认，请核对保存结果', 30_000)
    await capture('11-archive-response-loss', undefined)
    const keepArchived = await waitProjectState(runtime, keep.projectId, 'archived')
    assert.equal(keepArchived.lifecycleState, 'archived')
    await click('归档项目')
    await waitFor(renderer, `(document.body?.innerText ?? '').includes('项目已删除。')||(document.body?.innerText ?? '').includes('归档命令已接受')||!document.querySelector('[role=dialog]')`, '原身份重发', 30_000)
    const keepOperations = await apiOk(runtime, `/projects/${keep.projectId}/operations`)
    const keepArchives = keepOperations.items.filter(item => item.kind === 'archiveProject')
    assert.equal(keepArchives.length, 1, '同一幂等身份不得产生第二条归档事实')
    assert.ok(keepArchives[0].status === 'succeeded' || keepArchives[0].status === 'running')
    checkpoint(`E2E-7 响应丢失后按原操作身份找回同一条归档事实（状态 ${keepArchives[0].status}，共 ${keepArchives.length} 条）。`)

    const facts = {
      projectId: project.projectId,
      keptProjectId: keep.projectId,
      automationId: automation.automationId,
      batchId: batch.batchId,
      batchTerminal: batchTerminal.batch.status,
      taskTerminal: finished.items[0].status,
      archiveBlockers: blockedImpact.blockers.map(item => ({ code: item.code, state: item.state })),
      archivedExport: { name: exported.name, size: exported.size },
      tasksUnchanged: tasksAfter.total,
      archiveOperations: archiveFacts.length,
      restoreOperations: restoreFacts.length,
      referencedProfileRefusals: profileError.details?.references ?? [],
      remainingProjectId: keep.projectId,
      note: '项目、表、字段、记录与自动化均由界面创建；浏览器资源与工作流文档是明确标注的测试夹具；执行核心为隔离 QA 执行器。',
    }
    const result = await report('passed', undefined, facts)
    console.log(JSON.stringify({ status: result.status, scope: result.scope, runId, workspace, evidence, screenshots: screenshots.length, checkpoints: checkpoints.length }, null, 2))
    if (options.manual) {
      await applyManualInjections(runtime)
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
    console.error(`PM8_QA_FAILURE ${join(evidence, 'report.json')}`)
    console.error(JSON.stringify({ status: result.status, error: message }, null, 2))
    throw error
  } finally {
    if (!options.manual) await shutdown()
  }
}


if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  await main()
}
