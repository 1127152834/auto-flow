// Reuses historical audit scenarios against a new, exclusively owned workspace.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, realpath, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { connectCdp, launchElectron, waitFor, waitForProjectPage } from '../../../scripts/electron-cdp.mjs'
import { stop } from '../../../scripts/smoke-sidecar.mjs'
import { projectSmokeOptions } from '../../../scripts/smoke-project-management.mjs'

projectSmokeOptions([]) // Reject all QA service, renderer and picker substitutions.
const root = resolve(import.meta.dirname, '../../..')
const output = join(import.meta.dirname, 'ui-current')
await mkdir(output) // Refuse to replace previous acceptance evidence.
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow 修复回归-')))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'reduce' } }))
const kernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? join(process.env.HOME, 'Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2')
await mkdir(join(workspace, 'data/kernels'), { recursive: true })
execFileSync('cp', ['-cR', kernel, join(workspace, 'data/kernels', basename(kernel))])
const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
const report = { startedAt: new Date().toISOString(), head, platform: process.platform, arch: process.arch, workspace, boundary: 'Built Electron + production Python sidecar + SQLite. UI project creation, real repository metadata written via authenticated API, UI readback and navigation. No fake provider or executor.', checks: [], observations: [], consoleErrors: [] }
let desktop, cdp, native, studio, service, project, table, fields, records
const projectName = `AutoFlow 源码审计 ${head.slice(0, 8)}`
async function capture(name) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(output, `${name}.png`), data, 'base64')
  const snapshot = await cdp.evaluate(`({hash:location.hash,text:document.body.innerText,viewport:[innerWidth,innerHeight],width:document.documentElement.scrollWidth,alerts:[...document.querySelectorAll('[role=alert]')].map(e=>e.textContent)})`)
  await writeFile(join(output, `${name}.json`), JSON.stringify(snapshot, null, 2))
  return snapshot
}
async function check(name, fn) {
  const start = Date.now()
  try { const detail = await fn(); report.checks.push({ name, status: 'passed', ms: Date.now() - start, detail }); console.log(`PASS ${name}`); return true }
  catch (error) { report.checks.push({ name, status: 'failed', ms: Date.now() - start, error: String(error.stack ?? error) }); console.log(`FAIL ${name}: ${error.message}`); await capture(`failure-${report.checks.length}`).catch(() => {}); if (studio) await writeFile(join(output, `studio-failure-${report.checks.length}.txt`), await studio.evaluate('document.body.innerText').catch(() => 'unavailable')); return false }
  finally { await writeFile(join(output, 'result.json'), JSON.stringify(report, null, 2)) }
}
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  cdp = desktop.cdp
  cdp.socket.addEventListener('message', event => {
    const msg = JSON.parse(event.data)
    if (msg.method === 'Runtime.exceptionThrown') report.consoleErrors.push(msg.params.exceptionDetails.text)
  })
  await cdp.command('Runtime.enable')
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron = process.getBuiltinModule('module').createRequire(process.cwd() + '/package.json')('electron'); true")
  service = await waitFor(cdp, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'?r.sidecar:null})()`, 'production sidecar ready', 60_000)
  await waitFor(cdp, "document.body.innerText.includes('本地服务正常')", 'connected UI')
}
async function click(text, selector = 'button', page = cdp) {
  const point = await waitFor(page, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length&&!e.disabled&&(e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}));if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `click ${text}`)
  for (const type of ['mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
}
async function fill(selector, value) {
  await waitFor(cdp, `Boolean(document.querySelector(${JSON.stringify(selector)}))`, selector)
  await cdp.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select()})()`)
  await cdp.command('Input.insertText', { text: value })
}
async function api(path, { method = 'GET', body, key = randomUUID(), status = 200, prefix = '/api/v1' } = {}) {
  const response = await fetch(`${service.baseUrl}${prefix}${path}`, { method, headers: { 'x-autoflow-token': service.token, 'Content-Type': 'application/json', 'Idempotency-Key': key }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(20_000) })
  const result = await response.json()
  assert.equal(response.status, status, `${method} ${path}: ${JSON.stringify(result)}`)
  return result
}
async function navigate(hash) {
  await cdp.evaluate(`location.hash=${JSON.stringify(hash)}`)
  await waitFor(cdp, `location.hash===${JSON.stringify(hash)}&&!document.querySelector('main [role=progressbar]')`, 'route settled')
}
try {
  if (!await check('UI-01 真实应用启动与认证', async () => {
    await launch()
    const unauth = await fetch(`${service.baseUrl}/api/v1/projects`)
    assert.equal(unauth.status, 401)
    await capture('01-started')
  })) throw new Error('No real application session')
  if (!await check('UI-02 通过界面创建本仓库审计项目', async () => {
    await click('项目', '[aria-label="全局导航"] button')
    await click('新建项目')
    await waitFor(cdp, "document.activeElement?.id==='project-name'", 'autofocus')
    await fill('#project-name', projectName)
    await fill('#project-description', `当前代码 ${head}；真实源文件体积与 SHA-256，2026-09-28 审计。`)
    await click('创建项目')
    await waitForProjectPage(cdp)
    project = (await api('/projects')).items.find(p => p.name === projectName)
    assert.ok(project)
    await capture('02-created-project')
  })) throw new Error('No audit project')
  if (!await check('UI-03 实际仓库文件元数据入库与幂等', async () => {
    table = await api(`/projects/${project.projectId}/tables`, { method: 'POST', body: { name: '仓库文件清单', sourceKind: 'local' }, status: 201 })
    const prefix = `/projects/${project.projectId}/tables/${table.tableId}`
    fields = []
    for (const [key, name] of [['path', '源文件路径'], ['bytes', '字节数'], ['sha256', 'SHA-256']]) {
      const current = await api(prefix)
      const result = await api(`${prefix}/fields`, { method: 'POST', body: { definition: { key, name, type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: current.tableRevision } })
      fields.push(result.field.ref.fieldId)
    }
    records = []
    const manifest = []
    for (const path of ['README.md', 'package.json', 'apps/backend/pyproject.toml', 'docs/PROJECT_STRUCTURE.md', 'AGENTS.md']) {
      const data = await readFile(join(root, path))
      const values = [path, String((await stat(join(root, path))).size), createHash('sha256').update(data).digest('hex')]
      const body = { datasetGeneration: table.datasetGeneration, values: fields.map((fieldId, i) => ({ fieldId, value: values[i] })) }
      const key = randomUUID()
      const record = await api(`${prefix}/records`, { method: 'POST', body, key, status: 201 })
      assert.deepEqual(await api(`${prefix}/records`, { method: 'POST', body, key }), record)
      records.push(record); manifest.push({ path, bytes: Number(values[1]), sha256: values[2] })
    }
    await writeFile(join(output, 'source-manifest.json'), JSON.stringify(manifest, null, 2))
    const page = await api(`${prefix}/records?datasetGeneration=${table.datasetGeneration}&pageSize=20`)
    assert.equal(page.total, manifest.length)
    await navigate(`#/projects/${project.projectId}/data/${table.tableId}/records`)
    await waitFor(cdp, "document.body.innerText.includes('README.md')&&document.body.innerText.includes('pyproject.toml')", 'real records rendered')
    await capture('03-file-records')
    return { rows: manifest.length }
  })) throw new Error('Real data setup failed')
  await check('UI-04 记录详情真实读取', async () => {
    const r = records[0]
    await navigate(`#/projects/${project.projectId}/data/${table.tableId}/records/${table.datasetGeneration}/${r.ref.recordKey.type}/${Buffer.from(r.ref.recordKey.value).toString('base64url')}`)
    await waitFor(cdp, "Boolean(document.querySelector('[aria-label=记录详情]'))&&document.body.innerText.includes('README.md')", 'record details')
    await capture('04-record-detail')
  })
  await check('UI-04b 真实界面编辑源码路径并持久化', async () => {
    await click('编辑记录')
    await fill('input[aria-label="源文件路径"]', join(root, 'README.md'))
    await click('保存修改')
    await waitFor(cdp, "Boolean(document.querySelector('[aria-label=记录详情]'))", 'saved detail')
    const record = await api(`/projects/${project.projectId}/tables/${table.tableId}/records/${Buffer.from(records[0].ref.recordKey.value).toString('base64url')}?datasetGeneration=${table.datasetGeneration}&recordKeyType=${records[0].ref.recordKey.type}`)
    assert.equal(record.values.find(v => v.fieldId === fields[0]).value, join(root, 'README.md'))
    assert.equal(record.contentRevision, records[0].contentRevision + 1)
    await capture('04b-edited-record')
  })
  for (const [tab, name] of [['overview', '概览'], ['automations', '自动化'], ['runs', '运行记录'], ['statistics', '统计'], ['data', '数据'], ['environments', '环境']]) {
    await check(`UI-project-${tab} 项目${name}`, async () => {
      await navigate(`#/projects/${project.projectId}/${tab}`)
      await waitFor(cdp, `document.querySelector('[aria-label="项目功能"] [aria-current=page]')?.textContent.trim()===${JSON.stringify(name)}`, name)
      return await capture(`project-${tab}`)
    })
  }
  for (const tab of ['records', 'fields', 'statuses', 'source', 'settings']) {
    await check(`UI-table-${tab} 数据表页签`, async () => {
      await navigate(`#/projects/${project.projectId}/data/${table.tableId}/${tab}`)
      await waitFor(cdp, "document.body.innerText.includes('仓库文件清单')", 'table visible')
      return await capture(`table-${tab}`)
    })
  }
  for (const [route, name] of [['dashboard', '总览'], ['profiles', '浏览器配置'], ['android', '安卓设备'], ['proxies', '代理管理'], ['models', '模型管理'], ['lab', '实验室'], ['settings', '设置']]) {
    await check(`UI-global-${route} 全局${name}`, async () => {
      await click(name, route === 'settings' ? 'header button' : '[aria-label="全局导航"] button')
      await waitFor(cdp, `location.hash===${JSON.stringify(`#/${route}`)}`, name)
      await waitFor(cdp, "!document.querySelector('main [role=progressbar]')", 'global settled')
      const snapshot = await capture(`global-${route}`)
      assert.ok(snapshot.text.length > 100)
      return { alerts: snapshot.alerts, width: snapshot.width, viewport: snapshot.viewport }
    })
  }
  await check('UI-05 原生200%缩放', async () => {
    await navigate(`#/projects/${project.projectId}/data/${table.tableId}/records`)
    await waitFor(cdp, "document.body.innerText.includes('README.md')", 'records')
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows().find(w=>!w.webContents.getURL().includes("view=automation-studio")).webContents.setZoomFactor(2)')
    const snapshot = await capture('05-zoom-200')
    assert.ok(snapshot.width <= snapshot.viewport[0] + 1, `overflow ${snapshot.width}/${snapshot.viewport[0]}`)
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows().find(w=>!w.webContents.getURL().includes("view=automation-studio")).webContents.setZoomFactor(1)')
  })
  await check('UI-06 Studio实际窗口和同一服务', async () => {
    await cdp.evaluate('window.autoflow.openAutomationStudio()')
    let target
    for (let n = 0; n < 100; n++) {
      target = (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('view=automation-studio'))
      if (target) break
      await new Promise(resolveWait => setTimeout(resolveWait, 100))
    }
    assert.ok(target)
    studio = await connectCdp(target.webSocketDebuggerUrl)
    assert.equal(await waitFor(studio, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'?r.sidecar.instanceId:null})()`, 'Studio service'), service.instanceId)
    const text = await waitFor(studio, "document.body.innerText.length>100?document.body.innerText:null", 'Studio loaded')
    const screenshot = await studio.command('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(output, '06-studio.png'), screenshot.data, 'base64')
    await writeFile(join(output, '06-studio.txt'), text)
    studio.close(); studio = undefined
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes("view=automation-studio")).close()')
  })
  await check('UI-06b 正式Studio真实JS worker脚本及持久结果', async () => {
    const profile = await api('/profiles', { method: 'POST', status: 201, body: { name: '源码审计运行配置', description: '公开内核，独立工作区', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [], browserVersion: basename(kernel).replace('chromium-', ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null } })
    const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'))
    const expected = { name: manifest.name, scripts: Object.keys(manifest.scripts).sort(), workspaces: manifest.workspaces }
    // QA calibration: persisted node.type is the module type; 'custom' is not a valid JS node and is not a product regression.
    const workflow = await api('/workflows', { prefix: '/api', method: 'POST', status: 201, body: { id: randomUUID(), clientRequestId: randomUUID(), name: '实际package.json脚本审计', projectId: project.projectId, nodes: [{ id: 'js-audit', type: 'js_script', position: { x: 100, y: 100 }, data: { moduleType: 'js_script', label: 'JS脚本', code: `function main(vars) { const pkg = ${JSON.stringify(manifest)}; return {name: pkg.name, scripts: Object.keys(pkg.scripts).sort(), workspaces: pkg.workspaces}; }`, resultVariable: 'source_audit' } }], edges: [], variables: [] } })
    await cdp.evaluate(`window.autoflow.openAutomationStudio(${JSON.stringify({ projectId: project.projectId, workflowId: workflow.id })})`)
    let target
    for (let n = 0; n < 100; n++) {
      target = (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('view=automation-studio'))
      if (target) break
      await new Promise(resolveWait => setTimeout(resolveWait, 100))
    }
    assert.ok(target)
    studio = await connectCdp(target.webSocketDebuggerUrl)
    await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value===${JSON.stringify(workflow.name)}`, 'real saved document loaded')
    await waitFor(studio, `!!document.querySelector('[aria-label="运行浏览器配置"] option[value="${profile.id}"]')&&!document.querySelector('[aria-label="运行浏览器配置"]').disabled`, 'real profile options')
    await studio.evaluate('document.querySelector(\'[aria-label="运行浏览器配置"]\').focus()')
    for (const key of ['ArrowDown', 'Enter']) for (const type of ['keyDown', 'keyUp']) await studio.command('Input.dispatchKeyEvent', { type, key, code: key, windowsVirtualKeyCode: key === 'ArrowDown' ? 40 : 13 })
    await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value===${JSON.stringify(profile.id)}`, 'real profile selected')
    await click('运行 (F5)', '[aria-label="运行 (F5)"]', studio)
    await click('运行 (F5)', '[role="menuitem"]', studio)
    let run
    for (let n = 0; n < 300; n++) {
      run = (await api(`/workflow-runs?documentId=${workflow.id}&cursor=0&limit=20`, { prefix: '/api' })).items[0]
      if (run && ['completed', 'failed', 'stopped', 'interrupted'].includes(run.status)) break
      await new Promise(resolveWait => setTimeout(resolveWait, 200))
    }
    assert.equal(run?.status, 'completed', JSON.stringify(run))
    const result = await api(`/workflow-runs/${run.runId}/results?cursor=0&limit=20`, { prefix: '/api' })
    assert.deepEqual(result.items.find(item => item.nodeId === 'js-audit').values.result, expected)
    await writeFile(join(output, '06b-js-result.json'), JSON.stringify({ expected, run, result }, null, 2))
    const screenshot = await studio.command('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(output, '06b-js-completed.png'), screenshot.data, 'base64')
    studio.close(); studio = undefined
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes("view=automation-studio")).close()')
  })
  await check('UI-07 服务重启与真实数据库持久化', async () => {
    const idleSamples = []
    for (let n = 0; n < 50; n++) {
      const snapshot = await api('/settings/runtime')
      idleSamples.push({ elapsedMs: n * 100, blockers: snapshot.blockers })
      if (snapshot.blockers.length === 0) break
      await new Promise(resolveWait => setTimeout(resolveWait, 100))
    }
    report.observations.push({ beforeRestart: idleSamples })
    await cdp.evaluate('window.autoflow.restartSidecar()')
    const previousInstance = service.instanceId
    service = await waitFor(cdp, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(previousInstance)}?r.sidecar:null})()`, 'new service generation', 60_000)
    assert.equal((await api(`/projects/${project.projectId}/tables/${table.tableId}`)).recordCount, records.length)
    await waitFor(cdp, "document.body.innerText.includes('README.md')&&document.body.innerText.includes('本地服务正常')", 'reconnected records')
    await capture('07-reconnected')
  })
  await check('UI-08 应用进程重启持久化', async () => {
    native.close(); cdp.close(); await stop(desktop.child)
    await launch()
    assert.equal((await api(`/projects/${project.projectId}/tables/${table.tableId}`)).recordCount, records.length)
    await navigate(`#/projects/${project.projectId}/data/${table.tableId}/records`)
    await waitFor(cdp, "document.body.innerText.includes('README.md')", 'after restart')
    await capture('08-app-restarted')
  })
} catch (error) { report.fatal = String(error.stack ?? error) }
finally {
  studio?.close(); native?.close(); cdp?.close(); await stop(desktop?.child)
  report.finishedAt = new Date().toISOString()
  report.status = report.fatal || report.checks.some(c => c.status === 'failed') ? 'failed' : 'passed'
  await writeFile(join(output, 'result.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ status: report.status, passed: report.checks.filter(c => c.status === 'passed').length, failed: report.checks.filter(c => c.status === 'failed').length, workspace }))
  process.exitCode = report.status === 'passed' ? 0 : 1
}
