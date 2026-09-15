import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, lstat, mkdir, mkdtemp, readFile, readdir, realpath, stat, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { pathToFileURL } from 'node:url'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')

export const PM4_V1_STEPS = Object.freeze([
  'UI 创建项目',
  'UI 创建人员表、邮箱表、账号表及业务资料',
  'UI 创建自动化并配置两个独立必填输入',
  'UI 启动一个数据任务',
  'UI 查看不可变原始输入与显式数据写入',
  '只读 HTTP 核对人员不变、邮箱状态改变、账号只新增一次',
])

export function parsePm4QaArgs(args) {
  const result = { manual: false, prepareOnly: false, selfTest: false }
  for (const value of args) {
    if (value === '--manual') result.manual = true
    else if (value === '--prepare-only') result.prepareOnly = true
    else if (value === '--self-test') result.selfTest = true
    else throw new Error(`unknown argument: ${value}`)
  }
  return result
}

export function isOwnedPm4Workspace(path, ownerPath, marker) {
  const offset = relative(resolve(ownerPath), resolve(path))
  return marker?.kind === 'pm4-v1-project-management-qa'
    && marker?.version === 1
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
  const options = parsePm4QaArgs(cliArgs)
  if (options.selfTest) {
    assert.equal(isOwnedPm4Workspace('/tmp/pm4-owner/workspace', '/tmp/pm4-owner', { kind: 'pm4-v1-project-management-qa', version: 1 }), true)
    assert.equal(PM4_V1_STEPS.length, 6)
    console.log('PM4 V1 QA helper self-test passed')
    return
  }

  const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm4-v1-qa-')))
  const workspace = join(owner, 'workspace')
  const marker = { kind: 'pm4-v1-project-management-qa', version: 1, createdAt: new Date().toISOString() }
  await mkdir(workspace)
  await writeFile(join(owner, '.pm4-v1-qa.json'), JSON.stringify(marker, null, 2))
  await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))

  const evidenceParent = join(root, 'docs/project-management/implementation/pm4/qa-runs')
  await mkdir(evidenceParent, { recursive: true })
  const evidence = await mkdtemp(join(evidenceParent, 'v1-'))
  const screenshots = []
  const checkpoints = []
  const boundary = { executor: 'fake', browser: 'notExecuted', studio: 'notExecuted' }
  let desktop
  let renderer
  let native

  const checkpoint = message => { checkpoints.push(message); console.log(message) }
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
      scope: status === 'passed' ? '管理侧通过，真实执行核心接入待验收' : 'PM4 V1 管理侧验收未通过',
      boundary,
      visualReview: 'pending',
      gitHead: head.trim(),
      sourceSha256: sourceHash.digest('hex'),
      platform: process.platform,
      arch: process.arch,
      owner,
      workspace,
      evidence,
      checkpoints,
      screenshots,
      facts,
      error,
      excluded: ['真实执行核心', 'Studio demo', '真实浏览器执行', 'Windows', '其他架构', '打包应用', '用户手动执行结果'],
      createdAt: new Date().toISOString(),
    }
    await writeFile(join(evidence, 'result.json'), `${JSON.stringify(result, null, 2)}\n`)
    return result
  }

  async function launch() {
    const previous = process.env.AUTOFLOW_PM4_QA
    const previousMode = process.env.AUTOFLOW_PM4_QA_MODE
    process.env.AUTOFLOW_PM4_QA = '1'
    process.env.AUTOFLOW_PM4_QA_MODE = 'b'
    try {
      desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
    } finally {
      if (previous === undefined) delete process.env.AUTOFLOW_PM4_QA
      else process.env.AUTOFLOW_PM4_QA = previous
      if (previousMode === undefined) delete process.env.AUTOFLOW_PM4_QA_MODE
      else process.env.AUTOFLOW_PM4_QA_MODE = previousMode
    }
    renderer = desktop.cdp
    native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate("globalThis.pm4Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm4Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await visible('本地服务正常', 30_000)
    const runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    assert.ok(isOwnedPm4Workspace(runtime.workspaceKey, owner, marker), 'QA 只能修改 marker 所有的隔离工作区')
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
    if (selector === '[role=tab]') text = ({ 记录: '数据记录', 字段: '字段与校验', 状态: '数据状态' })[text] ?? text
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

  async function capture(name, reference) {
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate(`({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})`)
    assert.ok(geometry.scrollWidth <= geometry.viewport.width + 1, `${name} 不能撑宽应用`)
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    const bytes = Buffer.from(data, 'base64')
    const file = join(evidence, `${name}.png`)
    await writeFile(file, bytes)
    screenshots.push({ name, file, reference, ...geometry, sha256: createHash('sha256').update(bytes).digest('hex'), visualReview: 'pending' })
  }

  async function api(runtime, path) {
    assert.ok(isOwnedPm4Workspace(runtime.workspaceKey, owner, marker))
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token }, signal: AbortSignal.timeout(10_000) })
    const body = await response.text()
    assert.ok(response.ok, `GET ${path}: ${response.status} ${body}`)
    return JSON.parse(body)
  }

  async function seedWorkflow(runtime) {
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
document=workflow_payload(sys.argv[2]); document['content']['name']='PM4 V1 隔离执行器资料'
created=WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(document,str(uuid4()))
print(created.workflow_id); factory.dispose()`
    const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, runtime.workspaceKey, workflowId], { cwd: root })
    return stdout.trim()
  }

  async function seedProfile(runtime) {
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1/profiles`, {
      method: 'POST',
      headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json' },
      body: JSON.stringify({ name: 'PM4 V1 隔离执行器资源', description: '仅作为管理端资源夹具', startUrl: 'about:blank', locale: null, timezone: null, geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: null, extensionPathsJson: [], expertArgsJson: [], browserVersion: runtime.qaKernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null }),
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
      assert.ok(isOwnedPm4Workspace(destination, owner, marker))
      await cp(source, destination, { recursive: true, dereference: false, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
      return basename(source).slice('chromium-'.length)
    }
    throw new Error('未找到已安装的公开版 CloakBrowser 内核；PM4 V1 不执行浏览器，但真实资源校验仍需要一个已安装内核夹具')
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
    let created = page.items.at(-1)
    if (initialStatus) {
      await click('', '[aria-label^="修改状态 "]')
      await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"记录业务状态\"]'))", 'record status editor')
      await click('', '[aria-label="记录业务状态"]')
      await click(initialStatus, '[role=option]')
      await click('保存状态')
      await waitFor(renderer, "!document.querySelector('[role=dialog]')", 'initial record status saved')
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
    await input('#data-table-description', `${name}用于 PM4 V1 三表链`)
    await click('创建数据表')
    await waitFor(renderer, "Boolean(document.querySelector('[aria-label=\"返回数据表\"]'))", 'table detail route')
    const schema = await saveFields(runtime, projectId, name, fields)
    if (statuses.length) {
      await click('状态', '[role=tab]')
      for (const status of statuses) {
        await click('新增状态')
        await input('#status-name', status)
        await click('创建状态')
        await waitFor(renderer, "!document.querySelector('#status-editor-form')", 'status saved')
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

  try {
    const qaKernelVersion = await installQaKernel()
    const runtime = await launch()
    runtime.qaKernelVersion = qaKernelVersion
    const workflowId = await seedWorkflow(runtime)
    const profileId = await seedProfile(runtime)
    await capture('00-isolated-ready', '00-projects/100-projects-prototype-5238b4.png')
    if (options.prepareOnly) {
      const result = await report('prepared', undefined, { workflowId, profileId, preparation: '隔离工作区、QA sidecar、工作流和浏览器资源夹具已准备；尚未创建任何项目业务对象。' })
      console.log(JSON.stringify(result, null, 2))
      return
    }

    await click('项目')
    await click('新建项目')
    await input('#project-name', 'PM4 三表链验收')
    await input('#project-description', '两个必要输入、显式状态写入和账号新增')
    await click('创建项目')
    await visible('项目资料')
    const project = (await api(runtime, '/projects?q=PM4%20三表链验收')).items[0]
    assert.ok(project)
    checkpoint('UI 已创建项目；只读 GET 找回同一真实项目。')

    await click('数据', '[aria-label="项目功能"] button')
    await visible('还没有数据表')
    const person = await createTable(runtime, project.projectId, '人员', [{ key: 'name', name: '姓名', required: true }], [{ values: { name: '张三' } }])
    const email = await createTable(runtime, project.projectId, '邮箱', [{ key: 'email', name: '邮箱地址', required: true }], [{ values: { email: 'zhangsan@example.test' }, status: '待使用' }], ['待使用', '已使用'])
    const account = await createTable(runtime, project.projectId, '账号', [
      { key: 'person', name: '人员', required: true },
      { key: 'email', name: '邮箱', required: true },
      { key: 'result', name: '网页结果', required: true },
    ])
    const personBefore = canonicalRecord(person.records[0])
    const emailBefore = canonicalRecord(email.records[0])
    checkpoint('UI 已创建三张表、必要字段、人员/邮箱记录及待使用/已使用状态；账号表为空。')
    await wait(2800)
    await capture('01-three-tables', '05-data/001-data-v1-approved-ca940d.png')

    await click('自动化', '[aria-label="项目功能"] button')
    await click('新建自动化')
    await input('[aria-label="自动化名称"]', '三表资料处理')
    await input('[aria-label="用途说明"]', '选择人员和邮箱，写入邮箱状态并新增账号')
    await click('关联工作流', '[role=combobox]')
    await click('PM4 V1 隔离执行器资料', '[role=option]')
    await click('输入与参数', '[role=tab]')
    await click('添加数据输入')
    await click('添加数据输入')
    await configureInput('人员输入', '人员', 0)
    await configureInput('邮箱输入', '邮箱', 1)
    await click('资源与环境', '[role=tab]')
    await click('浏览器配置来源', '[role=combobox]')
    await click('指定浏览器配置', '[role=option]')
    await click('浏览器配置', '[role=combobox]')
    await click('PM4 V1 隔离执行器资源', '[role=option]')
    await click('保存配置')
    await visible('自动化已创建', 30_000)
    checkpoint('UI 已创建自动化并配置两个 independent + required 数据输入。')
    await click('输入与参数', '[role=tab]')
    await waitFor(renderer, `(()=>{const values=[...document.querySelectorAll('input')].map(input=>input.value);return values.includes('人员输入')&&values.includes('邮箱输入')})()`, '两个必要输入卡片', 30_000)
    await wait(2800)
    await capture('02-two-required-inputs', 'docs/prototype/project-management-pm3/automation-detail-inputs.png')

    await click('启动运行')
    await visible('启动自动化')
    await input('[aria-label="本次任务数"]', '1')
    await visible('人员输入')
    await visible('邮箱输入')
    await renderer.evaluate(`(() => { const dialog = document.querySelector('[role="dialog"]'); if (dialog) dialog.scrollTop = 0 })()`)
    await capture('03-input-preview', 'docs/prototype/project-management-pm3/batch-start-dialog.png')
    await click('启动 1 个任务')
    await visible('本批次任务', 30_000)
    const batches = await api(runtime, `/projects/${project.projectId}/batches?pageSize=10`)
    assert.equal(batches.total, 1)
    const batch = batches.items[0]
    const terminal = await waitBatchTerminal(runtime, project.projectId, batch.batchId)
    assert.equal(terminal.batch.status, 'completed')
    const tasks = await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)
    assert.equal(tasks.total, 1)
    const taskSummary = tasks.items[0]
    assert.equal(taskSummary.status, 'succeeded')
    await wait(2800)
    await capture('04-batch-completed', '03-runs/004-batch-detail-approved-459f25.png')

    await click(`查看任务`, `tbody tr button`)
    await visible('输入与输出')
    await click('输入与输出', '[role=tab]')
    await visible('原始数据输入')
    await visible('项目数据操作')
    for (const label of ['查询记录', '读取记录', '编辑记录', '删除记录', '变更状态', '新增记录', '新增字段', '确保字段', '修改字段']) await visible(label)
    await waitFor(renderer, `(()=>{const table=document.querySelector('table[aria-label="数据输入预览结果"]');const text=table?.innerText??'';return table?.querySelectorAll('tbody tr').length===2&&text.includes('人员输入')&&text.includes('邮箱输入')&&text.includes('张三')&&text.includes('zhangsan@example.test')})()`, '两条不可变原始输入显示在输入表格', 30_000)
    await waitFor(renderer, `(()=>{const table=document.querySelector('table[aria-label="项目数据操作结果"]');const text=table?.innerText??'';return table?.querySelectorAll('tbody tr').length>=9&&text.includes('记录 ·')&&text.includes('字段 QA 备注')&&text.includes('字段 执行备注')})()`, '提交事实和稳定引用显示在数据操作表格', 30_000)
    await wait(2800)
    await capture('05-task-input-output', '03-runs/006-task-input-output-approved-7af0aa.png')
    await renderer.evaluate(`(()=>{document.querySelector('table[aria-label="数据输入预览结果"]')?.scrollIntoView({block:'center'});return true})()`)
    await wait(300)
    await capture('05a-task-original-inputs', '03-runs/006-task-input-output-approved-7af0aa.png')
    await renderer.evaluate(`(()=>{document.querySelector('table[aria-label="项目数据操作结果"] tbody tr:last-child')?.scrollIntoView({block:'center'});return true})()`)
    await wait(300)
    await capture('05b-task-data-operation-tail', '03-runs/006-task-input-output-approved-7af0aa.png')
    const task = await api(runtime, `/projects/${project.projectId}/tasks/${taskSummary.taskId}`)
    const events = await api(runtime, `/projects/${project.projectId}/tasks/${taskSummary.taskId}/events?afterSequence=0`)
    const markerEvent = events.items.find(item => item.kind === 'output' && item.payload?.value?.executor === 'fake')
    assert.deepEqual(markerEvent?.payload?.value, boundary)
    assert.equal(task.inputSnapshot.inputs.length, 2)
    const dataWriteKinds = new Set(task.dataWrites.map(item => item.kind))
    assert.deepEqual(dataWriteKinds, new Set(['query', 'read', 'recordUpdated', 'recordDeleted', 'statusChange', 'recordCreated', 'fieldAdded', 'fieldEnsured', 'fieldModified']))

    const personAfter = (await api(runtime, `/projects/${project.projectId}/tables/${person.table.tableId}/records?datasetGeneration=${encodeURIComponent(person.table.datasetGeneration)}`)).items[0]
    const emailAfter = (await api(runtime, `/projects/${project.projectId}/tables/${email.table.tableId}/records?datasetGeneration=${encodeURIComponent(email.table.datasetGeneration)}`)).items[0]
    const accountsAfter = (await api(runtime, `/projects/${project.projectId}/tables/${account.table.tableId}/records?datasetGeneration=${encodeURIComponent(account.table.datasetGeneration)}`)).items
    assert.deepEqual(canonicalRecord(personAfter), personBefore, '人员记录必须完整保持不变')
    assert.deepEqual(emailAfter.values, emailBefore.values, '邮箱内容不因状态写入改变')
    assert.equal(emailAfter.contentRevision, emailBefore.contentRevision)
    assert.ok(emailAfter.statusRevision > emailBefore.statusRevision)
    const statuses = (await api(runtime, `/projects/${project.projectId}/tables/${email.table.tableId}/statuses`)).items
    assert.equal(statuses.find(item => item.statusId === emailBefore.statusId)?.name, '待使用')
    assert.equal(statuses.find(item => item.statusId === emailAfter.statusId)?.name, '已使用')
    assert.equal(accountsAfter.length, 1, '账号记录必须只新增一次')
    const accountFields = (await api(runtime, `/projects/${project.projectId}/tables/${account.table.tableId}/fields`)).items
    const resultFieldId = accountFields.find(item => item.key === 'result')?.ref.fieldId
    const accountValues = accountsAfter[0].values
    const resultValue = Array.isArray(accountValues)
      ? accountValues.find(item => item.fieldId === resultFieldId)?.value
      : accountValues[resultFieldId]
    assert.equal(resultValue, 'PM4-B-UPDATED')
    assert.equal(accountFields.find(item => item.key === 'qa_note')?.name, '执行备注')
    checkpoint('真实管理 API/SQLite 事实已核对：人员不变、邮箱最终为已使用、账号恰好一条且被显式更新，任务展示查询、读取、增改删、状态清空/设置及字段新增/确保/修改证据。')

    const facts = { projectId: project.projectId, batchId: batch.batchId, taskId: taskSummary.taskId, personBefore, personAfter: canonicalRecord(personAfter), emailBefore, emailAfter: canonicalRecord(emailAfter), accountCount: accountsAfter.length, taskInputAliases: task.inputSnapshot.inputs.map(item => item.alias), dataWrites: task.dataWrites, executionBoundary: markerEvent.payload.value }
    await writeFile(join(evidence, 'v1-facts.json'), `${JSON.stringify(facts, null, 2)}\n`)
    const result = await report('passed', undefined, facts)
    console.log(JSON.stringify(result, null, 2))

    if (options.manual) {
      console.log('应用保持打开。当前结果仅表示管理侧通过，真实执行核心接入待验收。按 Ctrl+C 退出。')
      await new Promise(() => {})
    }
  } catch (error) {
    if (renderer) {
      try { await capture('99-failure', undefined) } catch { /* preserve the original error */ }
    }
    const message = error instanceof Error ? error.stack ?? error.message : String(error)
    const result = await report('failed', message)
    console.error(`PM4_V1_QA_FAILURE ${join(evidence, 'result.json')}`)
    console.error(JSON.stringify(result, null, 2))
    throw error
  } finally {
    if (!options.manual) await shutdown()
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) await main()
