// PM5 environment pages through real Electron clicks on an isolated workspace.
//
// Real here: Electron renderer clicks, the FastAPI sidecar the desktop starts,
// SQLite, the environment pages, and a copied CloakBrowser kernel fixture.
// Not covered here: launching a headless/headed browser from a task (that path
// is proven by scripts/qa-pm5-browser-chain.py), the Studio demo, packaging.
import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { constants, createWriteStream } from 'node:fs'
import { cp, lstat, mkdir, mkdtemp, readdir, readFile, realpath, stat, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')

export const PM5_UI_STEPS = Object.freeze([
  '真实界面新建项目',
  '进入项目「环境」页并确认四个分区',
  '真实界面新建浏览器配置（使用已安装内核）',
  '环境页展示新建配置与空态入口',
  '截图 1440×1024 并核对不撑宽',
])

// Keep the last lines of the desktop log so a failed run carries its own trace
// instead of requiring a second reproduction to see why the page never updated.
async function desktopLogTail(path, lines = 40) {
  try {
    const text = await readFile(path, 'utf8')
    return text.split('\n').filter(Boolean).slice(-lines).join('\n')
  } catch {
    return ''
  }
}

export function parsePm5QaArgs(args) {
  const result = { manual: false, selfTest: false }
  for (const value of args) {
    if (value === '--manual') result.manual = true
    else if (value === '--self-test') result.selfTest = true
    else throw new Error(`unknown argument: ${value}`)
  }
  return result
}

export function isOwnedPm5Workspace(path, ownerPath, marker) {
  const offset = relative(resolve(ownerPath), resolve(path))
  return marker?.kind === 'pm5-project-management-qa'
    && marker?.version === 1
    && offset !== '..'
    && !offset.startsWith(`..${sep}`)
    && !isAbsolute(offset)
}

export async function main(cliArgs = process.argv.slice(2)) {
  const options = parsePm5QaArgs(cliArgs)
  if (options.selfTest) {
    assert.equal(isOwnedPm5Workspace('/tmp/pm5-owner/workspace', '/tmp/pm5-owner', { kind: 'pm5-project-management-qa', version: 1 }), true)
    assert.equal(PM5_UI_STEPS.length, 5)
    console.log('PM5 UI QA helper self-test passed')
    return
  }

  const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm5-ui-qa-')))
  const workspace = join(owner, 'workspace')
  const marker = { kind: 'pm5-project-management-qa', version: 1, createdAt: new Date().toISOString() }
  await mkdir(workspace)
  await writeFile(join(owner, '.pm5-qa.json'), `${JSON.stringify(marker, null, 2)}\n`)
  await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))

  const evidence = join(root, 'docs/project-management/implementation/pm5/qa-runs/2026-09-18')
  await mkdir(evidence, { recursive: true })
  const screenshots = []
  const checkpoints = []
  const facts = {}
  let desktop
  let renderer
  let native
  let runtime
  let desktopLogStream

  const checkpoint = message => { checkpoints.push(message); console.log(message) }
  const report = async (status, error) => {
    const { stdout: head } = await exec('git', ['rev-parse', 'HEAD'], { cwd: root })
    const result = {
      status,
      scenario: 'PM5 环境页真实界面验收',
      scope: status === 'passed'
        ? '管理侧及实际浏览器环境存取已验证；真实执行核心接入待验收'
        : 'PM5 界面验收未通过',
      evidenceType: '真实 Electron 渲染层点击 + 应用自启 FastAPI + SQLite + CloakBrowser',
      notEvidence: [
        '任务内真实浏览器执行（见 qa-pm5-browser-chain.py）',
        '真实工作流执行核心（本链用隔离执行器把任务保持在排队态）',
        'Studio demo',
      ],
      gitHead: head.trim(),
      platform: process.platform,
      arch: process.arch,
      owner,
      workspace,
      checkpoints,
      screenshots,
      facts,
      error,
      excluded: ['Windows', '其他架构', '打包应用', '用户手动执行结果'],
      createdAt: new Date().toISOString(),
    }
    await writeFile(join(evidence, 'ui-result.json'), `${JSON.stringify(result, null, 2)}\n`)
    console.log(JSON.stringify({ status, checkpoints, facts }, null, 2))
    return result
  }

  async function visible(text, timeout = 15_000) {
    return waitFor(renderer, `document.body?.innerText?.includes(${JSON.stringify(text)})`, text, timeout)
  }

  // Radix keeps the closing dialog in the DOM while it animates out, so a capture taken right
  // after a submit catches an overlay that is already on its way off screen. Wait for it to go.
  async function dialogClosed(timeout = 15_000) {
    return waitFor(renderer, `(()=>{const open=[...document.querySelectorAll('[role=dialog]')].some(e=>e.getClientRects().length);return open?null:true})()`, '弹层已关闭', timeout)
  }

  async function click(text, selector = 'button') {
    const point = await waitFor(renderer, `(()=>{const visible=e=>{const s=getComputedStyle(e);return e.getClientRects().length&&!e.disabled&&s.display!=='none'&&s.visibility!=='hidden'&&s.pointerEvents!=='none'};const label=e=>{if(e.getAttribute('aria-label'))return e.getAttribute('aria-label');const copy=e.cloneNode(true);copy.querySelectorAll?.('[aria-hidden=true]').forEach(node=>node.remove());return copy.textContent.trim()};const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>visible(e)&&(${JSON.stringify(text)}===''||label(e)===${JSON.stringify(text)}));if(!items.length)return null;const hit=e=>{const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return x>=0&&x<=innerWidth&&y>=0&&y<=innerHeight&&e.contains(document.elementFromPoint(x,y))};const e=items.find(hit)??items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `${selector} ${text}`)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(160)
  }

  async function input(selector, value) {
    await waitFor(renderer, `document.querySelector(${JSON.stringify(selector)})?.getClientRects().length>0`, selector)
    await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.focus();e.select();return true})()`)
    await renderer.command('Input.insertText', { text: value })
    await wait(90)
  }

  // Radix Select renders a placeholder entry as the first [role=option], so
  // "click the first option" silently picks the empty placeholder. Match the
  // option by text and click that exact element.
  async function clickOptionContaining(text) {
    const label = `包含「${text}」的下拉选项`
    const point = await waitFor(renderer, `(()=>{const items=[...document.querySelectorAll('[role=option]')].filter(e=>e.getClientRects().length&&e.getAttribute('aria-disabled')!=='true');const hit=items.find(e=>e.textContent.trim().includes(${JSON.stringify(text)}));if(!hit)return null;hit.scrollIntoView({block:'center'});const r=hit.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return hit.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, label, 15_000)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(160)
  }

  // React keeps the value in its own state, so clearing an input has to go through the
  // native value setter plus a bubbling input event; assigning .value alone is ignored.
  async function clearInput(selector) {
    await waitFor(renderer, `document.querySelector(${JSON.stringify(selector)})?.getClientRects().length>0`, selector)
    await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(e,'');e.dispatchEvent(new Event('input',{bubbles:true}));return true})()`)
    await wait(90)
  }

  // Toasts linger for 2.6s and would cover the panel a structural screenshot is about, so the
  // page-level captures dismiss them through their own close button first.
  async function dismissToasts() {
    for (let attempt = 0; attempt < 8; attempt++) {
      const open = await renderer.evaluate(`[...document.querySelectorAll('[aria-label="关闭通知"]')].filter(e=>e.getClientRects().length).length`)
      if (!open) return
      await click('关闭通知', 'button')
      await wait(220)
    }
  }

  async function capture(name) {
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate('({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})')
    assert.ok(geometry.scrollWidth <= geometry.viewport.width + 1, `${name} 不能撑宽应用`)
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    const bytes = Buffer.from(data, 'base64')
    await writeFile(join(evidence, `${name}.png`), bytes)
    screenshots.push({ name, file: join(evidence, `${name}.png`), ...geometry })
    return geometry
  }

  // Click the first visible element whose text contains `text`.
  async function clickContains(text, selector = 'button, [role=button], a') {
    const label = `包含「${text}」的 ${selector}`
    const point = await waitFor(renderer, `(()=>{const items=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled&&getComputedStyle(e).pointerEvents!=='none'&&e.textContent.trim().includes(${JSON.stringify(text)}));if(!items.length)return null;const e=items.find(candidate=>{const r=candidate.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return x>0&&y>0&&x<innerWidth&&y<innerHeight&&candidate.contains(document.elementFromPoint(x,y))})??items[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, label, 20_000)
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(160)
  }

  // Directory rows keep their actions behind the row menu, the way the artboard does.
  // Open the first visible row menu so the following click can pick a menu item.
  async function openFirstRowMenu() {
    const point = await waitFor(renderer, `(()=>{const items=[...document.querySelectorAll('button[aria-label^="更多 "]')].filter(e=>e.getClientRects().length&&!e.disabled);const e=items[0];if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, '持久环境行更多菜单')
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    await wait(160)
  }

  async function api(path, init) {
    assert.ok(isOwnedPm5Workspace(runtime.workspaceKey, owner, marker), 'QA 只能操作 marker 所有的隔离工作区')
    facts.workspaceKey = runtime.workspaceKey
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, {
      ...init,
      headers: { 'x-autoflow-token': runtime.sidecar.token, ...(init?.body ? { 'content-type': 'application/json' } : {}), ...init?.headers },
      signal: AbortSignal.timeout(20_000),
    })
    const body = await response.text()
    assert.ok(response.ok, `${init?.method ?? 'GET'} ${path}: ${response.status} ${body}`)
    return body ? JSON.parse(body) : undefined
  }

  // A workflow document is test material only: the automation, its environment
  // policy and the run itself are all created through the renderer.
  async function seedWorkflow(name) {
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
    const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, runtime.workspaceKey, workflowId, name], { cwd: root, timeout: 180_000 })
    return stdout.trim()
  }

  // A scene waiting for a human cannot be produced by the isolated test executor, so the
  // artboard state is materialised as an explicitly labelled fixture row in the throw-away QA
  // workspace and removed again right after the capture. Every query, page and action that
  // renders it stays the production code path.
  const fixtureIds = []
  async function injectWaitingManualScene(projectId, profileId, taskId, runId, mode = 'waiting') {
    const code = `import json, sqlite3, sys, uuid
from datetime import datetime, timedelta
db, project_id, profile_id, task_id, run_id = sys.argv[1:6]
mode = sys.argv[6]
now = datetime.now()
stamp = lambda value: value.strftime('%Y-%m-%d %H:%M:%S.%f')
instance_id, manual_id = str(uuid.uuid4()), str(uuid.uuid4())
connection = sqlite3.connect(db)
# 运行状态必须与人工事项一致，否则截图里的「排队中 + 查看事项」会自相矛盾。
# 这里只改一次性 QA 工作区，并把原状态一并返回给清理步骤。
run_row = connection.execute('select status from workflow_runs where id = ?', (run_id,)).fetchone()
run_status = run_row[0] if run_row else None
# 超时终态必须让运行状态与人工事项一致，否则截图会出现「等待人工 + 已超时」自相矛盾。
injected_run_status = 'timed_out' if mode == 'expired' else 'waiting_manual'
if run_status is not None:
    connection.execute("update workflow_runs set status = ?, status_revision = status_revision + 1 where id = ?", (injected_run_status, run_id,))
connection.execute(
    'insert into project_environment_instances (id, project_id, environment_id, state, source, source_content_generation, instance_use_generation, active_task_id, active_run_id, maintenance_operation_id, profile_id, identity_package, created_at, updated_at)'
    ' values (?, ?, null, ?, ?, null, 1, ?, ?, null, ?, ?, ?, ?)',
    (instance_id, project_id, 'retained_unsaved', 'newFromProfile', task_id, run_id, profile_id,
     json.dumps({'source': 'newFromProfile', 'profileId': profile_id}), stamp(now - timedelta(minutes=2)), stamp(now)),
)
connection.execute(
    'insert into project_manual_items (id, project_id, task_id, run_id, instance_id, checkpoint_revision, status, status_revision, expires_at, allowed_targets, resume_started, reason, created_at, updated_at)'
    ' values (?, ?, ?, ?, ?, 1, ?, 1, ?, ?, 0, ?, ?, ?)',
    (manual_id, project_id, task_id, run_id, instance_id, mode,
     stamp(now - timedelta(minutes=5) if mode == 'expired' else now + timedelta(minutes=13)),
     '[]', '确认提取内容' if mode == 'expired' else '待确认页面内容',
     stamp(now - timedelta(minutes=20) if mode == 'expired' else now - timedelta(minutes=2)), stamp(now)),
)
connection.commit()
connection.close()
print(json.dumps({'instanceId': instance_id, 'manualItemId': manual_id, 'runId': run_id, 'runStatus': run_status}))`
    const { stdout } = await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, join(runtime.workspaceKey, 'data', 'autoflow.sqlite3'), projectId, profileId, taskId, runId, mode], { cwd: root, timeout: 180_000 })
    const ids = JSON.parse(stdout.trim())
    fixtureIds.push(ids)
    return ids
  }

  async function removeInjectedManualScene() {
    if (!fixtureIds.length) return
    const code = `import json, sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
for row in json.loads(sys.argv[2]):
    connection.execute('delete from project_manual_items where id = ?', (row['manualItemId'],))
    connection.execute('delete from project_environment_instances where id = ?', (row['instanceId'],))
    if row.get('runStatus'):
        connection.execute('update workflow_runs set status = ? where id = ?', (row['runStatus'], row['runId']))
connection.commit()
connection.close()`
    await exec('uv', ['run', '--directory', 'apps/backend', 'python', '-c', code, join(runtime.workspaceKey, 'data', 'autoflow.sqlite3'), JSON.stringify(fixtureIds)], { cwd: root, timeout: 180_000 })
    fixtureIds.length = 0
  }

  // The real opener must leave a kernel process holding the instance work copy.
  async function browserHoldingInstance(instanceId) {
    const { stdout } = await exec('ps', ['-Ao', 'command'], { maxBuffer: 8 * 1024 * 1024 })
    // The desktop app nests its business workspace under the user-data dir, so
    // match the unique instance path suffix instead of assuming the prefix.
    const marker = join('environments', 'instances', instanceId)
    return stdout.split('\n').filter(line => line.includes(marker) && line.includes('Chromium')).slice(0, 2)
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
      await cp(source, destination, { recursive: true, dereference: false, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
      return basename(source).slice('chromium-'.length)
    }
    throw new Error('未找到已安装的公开版 CloakBrowser 内核夹具')
  }

  try {
    facts.kernelVersion = await installQaKernel()
    // PM5 hands a live task's work copy to the human, so the acceptance chain
    // runs the isolated management sidecar: real bootstrap, SQLite, environment
    // store and CloakBrowser opener/closer, but no batch executor that would
    // launch its own browser on the profile the human is logging into.
    const sidecarModule = process.env.AUTOFLOW_QA_SIDECAR_MODULE || 'tests.qa.pm5_sidecar'
    process.env.AUTOFLOW_QA_SIDECAR_MODULE = sidecarModule
    facts.sidecarModule = sidecarModule
    desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
    // The sidecar's own stdout/stderr carry the only traceback for a failed
    // open/save. The desktop pipes them here instead of into the repository:
    // an ephemeral QA directory, so a report can point at the trace without
    // keeping runtime state or credentials in the evidence tree.
    const desktopLog = join(owner, 'desktop.log')
    facts.desktopLog = desktopLog
    desktopLogStream = createWriteStream(desktopLog, { flags: 'a' })
    desktop.child.stdout.pipe(desktopLogStream)
    desktop.child.stderr.pipe(desktopLogStream)
    renderer = desktop.cdp
    native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate("globalThis.pm5Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm5Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await visible('本地服务正常', 30_000)
    runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    assert.ok(isOwnedPm5Workspace(runtime.workspaceKey, owner, marker), 'QA 只能操作 marker 所有的隔离工作区')
    facts.debugPort = new URL(desktop.debugOrigin).port

    await click('项目', 'a, button')
    await visible('新建项目', 20_000)
    await click('新建项目')
    await input('#project-name', 'PM5 环境界面验证')
    await click('创建项目')
    await visible('PM5 环境界面验证', 20_000)
    checkpoint('真实界面新建项目成功。')
    if (!(await renderer.evaluate("location.hash.includes('/projects/')"))) {
      await click('PM5 环境界面验证', '[role=button]')
    }
    await click('环境', 'button, [role=tab]')
    await visible('持久环境', 20_000)
    facts.environmentSections = await renderer.evaluate(`(()=>{const text=document.body.innerText;return ['运行环境','等待人工','持久环境','项目默认资源'].filter(label=>text.includes(label))})()`)
    assert.equal(facts.environmentSections.length, 4, '环境页必须有四个分区')
    facts.environmentRoute = await renderer.evaluate('location.hash')
    await capture('01-environment-workspace')
    checkpoint('环境页四个分区在真实界面可见。')

    await click('浏览器配置', 'a, button')
    await visible('浏览器配置', 20_000)
    await click('新建配置')
    await input('#profile-name', 'PM5 界面验证配置')
    await click('内核与代理', 'button, [role=tab]')
    await click('', '[aria-label="浏览器内核"]')
    const kernelOption = await waitFor(renderer, `(()=>{const items=[...document.querySelectorAll('[role=option]')].filter(e=>e.getClientRects().length);const hit=items.find(item=>item.textContent.includes(${JSON.stringify(facts.kernelVersion)}))??items.find(item=>item.textContent.includes('chromium'));if(!hit)return null;return hit.textContent.trim()})()`, '内核选项', 15_000)
    facts.kernelOption = kernelOption
    await clickOptionContaining(kernelOption)
    facts.kernelSelected = await waitFor(renderer, `(()=>{const t=document.querySelector('[aria-label="浏览器内核"]')?.textContent?.trim()??'';return t.includes(${JSON.stringify(facts.kernelVersion)})?t:null})()`, '内核已选中', 10_000)
    await capture('02-profile-kernel-selected')
    await click('创建配置')
    await visible('PM5 界面验证配置', 30_000)
    await dialogClosed()
    await capture('02-profile-created')
    checkpoint('真实界面新建浏览器配置成功。')

    const projectId = facts.environmentRoute.match(/projects\/([^/]+)/)[1]
    facts.projectId = projectId
    await click('项目', 'a, button')
    await visible('最近项目', 20_000)
    // 最近项目只列出真正打开过的项目；新建后必须从全部项目打开一次。
    await click('查看全部项目')
    await visible('PM5 环境界面验证', 20_000)
    await clickContains('PM5 环境界面验证')
    try {
      await click('环境', 'button, [role=tab]')
      await visible('持久环境', 20_000)
    } catch {
      facts.projectNavigation = 'hash'
      await renderer.evaluate(`location.hash = '#/projects/${projectId}/environments'`)
      await visible('持久环境', 20_000)
    }
    await capture('03-environment-after-profile')
    checkpoint('环境页在配置创建后仍正常渲染。')

    const workflowName = 'PM5 登录环境演示资料'
    facts.workflowId = await seedWorkflow(workflowName)

    await click('自动化', '[aria-label="项目功能"] button')
    await click('新建自动化')
    await input('[aria-label="自动化名称"]', 'PM5 登录环境演示')
    await input('[aria-label="用途说明"]', '指定浏览器配置创建临时环境，结束并保留登录环境')
    await click('关联工作流', '[role=combobox]')
    await click(workflowName, '[role=option]')
    await click('资源与环境', '[role=tab]')
    await click('浏览器配置来源', '[role=combobox]')
    await click('指定浏览器配置', '[role=option]')
    await click('浏览器配置', '[role=combobox]')
    await click('PM5 界面验证配置', '[role=option]')
    facts.environmentPolicy = await renderer.evaluate(`(()=>{const checked=[...document.querySelectorAll('input[type=radio]')].filter(item=>item.checked).map(item=>item.closest('label')?.textContent?.trim()??item.value);return checked})()`)
    await capture('04-automation-environment-policy')
    await click('保存配置')
    await visible('自动化已创建', 30_000)
    checkpoint('真实界面创建自动化，环境来源为指定浏览器配置。')

    await visible('启动运行', 30_000)
    await click('启动运行')
    await visible('启动自动化')
    await capture('05-start-dialog')
    await clickContains('个任务')
    try {
      await visible('本批次任务', 30_000)
    } catch (failure) {
      const recoverable = await renderer.evaluate(`[...document.querySelectorAll('button')].some(item=>item.textContent.trim()==='核对原操作'&&!item.disabled&&item.getClientRects().length)`)
      if (!recoverable) throw failure
      await click('核对原操作')
      await visible('本批次任务', 30_000)
      facts.startRecovery = '核对原操作'
    }
    const tasks = await api(`/projects/${projectId}/tasks?pageSize=20`)
    assert.ok(tasks.total >= 1, '启动运行必须产生任务事实')
    const task = tasks.items[0]
    facts.taskId = task.taskId
    facts.taskStatus = task.status
    checkpoint('真实界面启动运行并产生任务。')

    await click('环境', 'button, [role=tab]')
    await visible('运行环境', 20_000)
    await clickContains('运行环境', '[role=tab]')
    await visible('进入当前浏览器', 20_000)
    const instancePage = await api(`/projects/${projectId}/environment-instances?pageSize=20`)
    assert.ok(instancePage.total >= 1, '任务必须预约一个真实环境实例')
    const instance = instancePage.items[0]
    facts.instanceId = instance.instanceId
    facts.instanceState = instance.state
    await capture('06-running-environment')
    checkpoint('环境页运行环境列出真实任务实例。')

    await click('进入当前浏览器')
    // 07 must not be a byte-identical duplicate of 06, so capture the acknowledgement the
    // artboard pairs with the entry button before waiting on the real kernel process.
    await visible('已请求进入当前浏览器', 20_000)
    await capture('07-enter-current-browser')
    let holder = []
    for (let attempt = 0; attempt < 90 && holder.length === 0; attempt++) {
      holder = await browserHoldingInstance(instance.instanceId)
      if (holder.length === 0) await wait(1_000)
    }
    assert.ok(holder.length > 0, `进入当前浏览器必须真实启动 CloakBrowser 并占用 ${instance.instanceId} 工作副本`)
    assert.ok(
      holder[0].includes(`chromium-${facts.kernelVersion}`) && !holder[0].includes('.cloakbrowser'),
      `进入当前浏览器必须拉起配置声明的内核，实际：${holder[0].slice(0, 160)}`,
    )
    facts.browserHoldingInstance = holder[0].slice(0, 200)
    facts.browserKernel = holder[0].split(' --')[0]
    const opened = await api(`/projects/${projectId}/environment-instances/${instance.instanceId}`)
    facts.instanceStateAfterOpen = opened.state
    checkpoint('「进入当前浏览器」真实拉起内核进程并占用实例工作副本。')

    await renderer.evaluate(`location.hash = '#/projects/${projectId}/runs/tasks/${task.taskId}/logs'`)
    await visible('结束并保留', 30_000)
    await capture('08-task-end-panel')
    // The save is fenced by the run's execution generation, so the evidence has
    // to show which generation the user was looking at when they pressed End.
    const beforeEnd = await api(`/projects/${projectId}/tasks/${task.taskId}`)
    facts.runStatusBeforeEnd = beforeEnd.run?.status
    facts.runGenerationBeforeEnd = beforeEnd.run?.executionGeneration
    await click('结束并保留')
    let saved = 0
    for (let attempt = 0; attempt < 60; attempt++) {
      const environments = await api(`/projects/${projectId}/environments?pageSize=20`)
      saved = environments.total
      if (saved > 0) break
      await wait(1_000)
    }
    facts.savedEnvironments = saved
    const afterEnd = await api(`/projects/${projectId}/tasks/${task.taskId}`)
    facts.runStatusAfterEnd = afterEnd.run?.status
    facts.runGenerationAfterEnd = afterEnd.run?.executionGeneration
    assert.ok(saved >= 1, '结束并保留必须在环境目录留下一个真实保存环境')
    for (let attempt = 0; attempt < 60; attempt++) {
      const still = await browserHoldingInstance(instance.instanceId)
      if (still.length === 0) break
      await wait(1_000)
      if (attempt === 59) assert.fail('结束并保留必须真实关闭被占用的内核进程')
    }
    facts.closedAfterEnd = true
    await capture('09-environment-saved')
    checkpoint('任务页「结束并保留」保存登录环境并真实关闭原浏览器。')

    await renderer.evaluate(`location.hash = '#/projects/${projectId}/environments'`)
    await visible('持久环境', 20_000)
    await clickContains('持久环境', '[role=tab]')
    await visible('最近来源', 20_000)
    await dismissToasts()
    await capture('10-saved-environment-list')
    await openFirstRowMenu()
    await clickContains('查看环境', '[role=menuitem]')
    await visible('内容代次', 20_000)
    await dismissToasts()
    await capture('11-saved-environment-detail')
    // 100-rename-drawer / 100-rename-validation-conflict: the rename keeps the environment's
    // facts on screen behind a right-hand drawer, and an invalid name never reaches the server.
    await click('重命名', 'button')
    await visible('重命名环境', 20_000)
    await dismissToasts()
    await capture('16-rename-drawer')
    await clearInput('[aria-label="环境名称"]')
    await visible('名称需 1–36 个字符', 20_000)
    const renameSubmitDisabled = await renderer.evaluate(`document.querySelector('button[type=submit]')?.disabled === true`)
    assert.ok(renameSubmitDisabled, '重命名抽屉里的空名称必须阻止提交')
    await dismissToasts()
    await capture('17-rename-validation-blocked')
    await click('取消', 'button')
    await visible('放弃未保存的名称修改？', 20_000)
    await click('放弃修改', 'button')
    await dialogClosed()
    facts.renameValidation = '空名称被界面阻止，未发出请求'
    checkpoint('重命名抽屉保留环境事实，非法名称在提交前被阻止。')
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/environments'`)
    await visible('运行环境', 20_000)
    await clickContains('项目默认资源', '[role=tab]')
    await visible('项目默认资源', 20_000)
    await capture('12-project-defaults')
    await clickContains('等待人工', '[role=tab]')
    await capture('13-manual-items')
    checkpoint('环境页四个分区完成同视口截图。')

    // 003-manual-environment-list needs a scene that is actually waiting for a human. The
    // isolated test executor never reaches that checkpoint, so the row is injected into the
    // throw-away QA workspace, rendered by the production page and query, and deleted again.
    const live = await api(`/projects/${projectId}/environment-instances?pageSize=50`)
    const injectedIds = await injectWaitingManualScene(projectId, live.items[0].profileId, task.taskId, afterEnd.run.runId)
    facts.injectedFixtures = [`等待人工现场（${injectedIds.instanceId} / ${injectedIds.manualItemId}）为隔离 QA 工作区测试注入资料，截图后已删除`]
    await clickContains('运行环境', '[role=tab]')
    await click('刷新', 'button')
    await visible('需要人工处理 1', 20_000)
    await dismissToasts()
    await capture('18-manual-waiting-live')
    await clickContains('等待人工', '[role=tab]')
    await visible('进入人工处理', 20_000)
    await dismissToasts()
    await capture('19-manual-directory')

    // 03-runs 的人工画板：运行记录的「等待人工」页签与唯一一份人工详情。两者都走生产
    // 查询与生产页面，只是数据来自上面那份显式标记的测试注入资料。
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/runs/manual'`)
    await visible('运行记录', 20_000)
    await visible('等待原因', 20_000)
    await dismissToasts()
    await capture('20-manual-list-tab')
    await clickContains('查看事项', 'button')
    await visible('当前现场', 20_000)
    await visible('处理方式', 20_000)
    await dismissToasts()
    await capture('21-manual-detail')
    await clickContains('标记完成', 'label')
    await click('提交处理结果', 'button')
    await visible('将这条任务标记完成？', 20_000)
    await visible('标记完成不等于资料已保存，也不会自动写入业务数据。', 20_000)
    const confirmDisabled = await renderer.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='确认标记完成'&&b.disabled)`)
    assert.ok(confirmDisabled, '未勾选知情确认前不得提交「标记完成」')
    await dismissToasts()
    await capture('22-manual-complete-confirm')
    await click('取消', 'button')
    await dialogClosed()
    await clickContains('标记失败', 'label')
    await visible('失败说明', 20_000)
    const failureSubmitDisabled = await renderer.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='提交处理结果'&&b.disabled)`)
    assert.ok(failureSubmitDisabled, '未填写失败说明前不得提交「标记失败」')
    await dismissToasts()
    await capture('23-manual-failure-required')
    facts.manualDetail = '运行记录「等待人工」页签、人工详情、完成确认与失败必填均由生产页面渲染；提交会写回原任务'
    checkpoint('人工详情、完成二次确认与失败必填按原型呈现。')

    // 002-task-list：等待人工的任务行直接进入同一份人工详情，其它任务仍进入任务详情。
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/runs/tasks'`)
    await visible('任务记录', 20_000)
    await visible('查看事项', 20_000)
    await dismissToasts()
    await capture('24-task-list-manual-entry')
    await clickContains('查看事项', 'button')
    await visible('当前现场', 20_000)
    facts.manualEntry = '等待人工的任务行从「查看事项」进入同一份人工详情，其它任务仍进入任务详情'
    checkpoint('任务列表的人工入口指向同一份详情。')

    await renderer.evaluate(`location.hash = '#/projects/${projectId}/environments'`)
    await visible('运行环境', 20_000)
    await clickContains('等待人工', '[role=tab]')
    await visible('进入人工处理', 20_000)
    await removeInjectedManualScene()
    await click('刷新', 'button')
    await visible('当前没有等待人工处理的环境。', 20_000)
    facts.injectedFixtures.push('注入资料已在同一脚本内删除，清理后等待人工分区回到空态')
    checkpoint('等待人工现场按原型呈现，测试注入资料已清理。')

    // 020-manual-expired：保留时间已到的终态必须显示「处理结果」与历史现场，
    // 不能继续渲染不可用的提交表单。同样是显式标记的一次性注入资料。
    const expired = await injectWaitingManualScene(projectId, live.items[0].profileId, task.taskId, afterEnd.run.runId, 'expired')
    facts.expiredFixture = `超时终态（${expired.manualItemId}）为隔离 QA 工作区测试注入资料，运行状态随之置为 timed_out，截图后已删除`
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/runs/manual'`)
    await visible('运行记录', 20_000)
    await click('等待人工状态筛选', '[role=combobox]')
    await clickOptionContaining('已超时')
    await visible('已超时', 20_000)
    await dismissToasts()
    await capture('25-manual-expired-list')
    await clickContains('查看事项', 'button')
    await visible('处理结果', 20_000)
    await visible('保留时间已到，不能再提交人工处理。', 20_000)
    await visible('历史现场', 20_000)
    await visible('查看任务日志', 20_000)
    const expiredSubmit = await renderer.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='提交处理结果')`)
    assert.ok(!expiredSubmit, '超时终态不得显示「提交处理结果」')
    const expiredOpen = await renderer.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='打开环境')`)
    assert.ok(!expiredOpen, '超时终态不得显示「打开环境」')
    await dismissToasts()
    await capture('26-manual-expired-result')
    await removeInjectedManualScene()
    facts.injectedFixtures.push('超时终态注入资料已在同一脚本内删除，运行状态还原')
    checkpoint('超时终态显示处理结果与历史现场，不显示不可用的提交表单。')
    // 回到环境页的原始停靠点，后续可用性状态检查从这里继续。
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/environments'`)
    await visible('运行环境', 20_000)
    await clickContains('等待人工', '[role=tab]')
    await visible('当前没有等待人工处理的环境。', 20_000)

    // 010-runtime-availability-states requires 确实无数据 and 读取失败 to stay distinct. Block the
    // directory request once so the failure copy is captured as real evidence instead of a claim.
    await clickContains('持久环境', '[role=tab]')
    await visible('刷新', 20_000)
    await renderer.command('Network.enable')
    await renderer.command('Network.setBlockedURLs', { urls: ['*environments?q=*'] })
    await click('刷新', 'button')
    await visible('重试读取', 30_000)
    await capture('14-directory-read-failed')
    await renderer.command('Network.setBlockedURLs', { urls: [] })
    await click('重试读取', 'button')
    await visible('登录环境', 30_000)
    await capture('15-directory-read-recovered')
    checkpoint('读取失败与确实无数据分开呈现，重试后恢复真实数据。')

    return await report('passed', null)
  } catch (error) {
    try { await capture('99-failure') } catch { /* evidence capture is best effort */ }
    const diagnosis = await desktopLogTail(join(owner, 'desktop.log'))
    if (diagnosis) {
      facts.desktopLogTail = diagnosis
      console.error(`桌面日志尾部（${join(owner, 'desktop.log')}）：\n${diagnosis}`)
    }
    // The sidecar keeps its own stdout/stderr next to the data directory; that
    // trace is what explains a refused save or a service that restarted.
    const sidecarLog = join(workspace, 'logs', 'sidecar.log')
    facts.sidecarLog = sidecarLog
    const sidecarTail = await desktopLogTail(sidecarLog, 60)
    if (sidecarTail) {
      facts.sidecarLogTail = sidecarTail
      console.error(`本地服务日志尾部（${sidecarLog}）：\n${sidecarTail}`)
    }
    return await report('failed', `${error?.stack ?? error}`)
  } finally {
    desktopLogStream?.end()
    if (!options.manual) {
      renderer?.close()
      native?.close()
      await stop(desktop?.child).catch(() => undefined)
    } else {
      console.log(`手动模式：应用保持运行，隔离工作区 ${workspace}，调试端口 ${facts.debugPort}`)
    }
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  const result = await main()
  process.exitCode = !result || result.status === 'passed' ? 0 : 1
}
