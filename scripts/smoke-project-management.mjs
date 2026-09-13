import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { parseArgs } from 'node:util'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'
import { assertOutsideHistory } from './project-smoke-output.mjs'

// Only disposable workspaces are used. UI commands use the real local service.
const root = resolve(import.meta.dirname, '..')
const { values: options, tokens } = parseArgs({ options: { 'output-dir': { type: 'string' }, dev: { type: 'boolean' } }, tokens: true })
assert.equal(new Set(tokens.map(token => token.name)).size, tokens.length, 'duplicate option')
assert.ok(options['output-dir'] === undefined || options['output-dir'].trim(), '--output-dir requires a directory')
const historicalQa = join(root, 'docs/migration/project-management-pm1-qa')
const defaultParent = join(root, 'docs/migration/project-management-regression-qa')
if (!options['output-dir']) {
  await assertOutsideHistory(historicalQa, defaultParent)
  await mkdir(defaultParent, { recursive: true })
}
const qa = options['output-dir'] ? resolve(options['output-dir']) : await mkdtemp(join(defaultParent, 'run-'))
await assertOutsideHistory(historicalQa, qa)
await mkdir(qa, { recursive: true })
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm1-qa-')))
const otherWorkspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm1-other-')))
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(userData, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: userData, previousPath: otherWorkspace, preferences: { zoom: 100, motion: 'system' } }))
let desktop, native, main, devServer
const checks = []
const measurements = {}
const entry = options.dev ? 'development-url' : 'built-html'

try {
  if (options.dev) {
    const { resolveConfig } = await import('electron-vite')
    const { createServer } = await import('vite')
    const { config } = await resolveConfig({ root: join(root, 'apps/desktop') }, 'serve', 'development')
    devServer = await createServer({ ...config.renderer, root: join(root, 'apps/desktop/src/renderer'), server: { host: '127.0.0.1', port: 0 } })
    await devServer.listen()
    process.env.ELECTRON_RENDERER_URL = devServer.resolvedUrls.local[0]
  }
  await launch()
  await click('项目')
  await visible('还没有项目')
  await capture('empty')
  const a = await create('项目 A', '浏览器自动化配置与业务资料')
  await click('编辑项目')
  await input('#project-description', '修改后的项目 A')
  await click('保存')
  await closedForm()
  assert.equal((await api(`/projects/${a}`)).description, '修改后的项目 A')
  const edited = await api(`/projects/${a}`)
  assert.equal(edited.managementRevision, 2)
  await click('项目')
  const b = await create('项目 B', '另一项独立工作')
  checkpoint('UI creates A/B and edits A using persisted project revisions')
  await capture('overview')
  for (const tab of ['自动化', '运行记录', '统计', '环境']) { await click(tab); await visible(`${tab}暂未开放`) }
  await click('数据'); await visible('还没有数据表')
  await click('概览')
  await click('项目')
  await input('[aria-label="搜索项目"]', '修改后的项目 A')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 1 && document.querySelector('tbody')?.innerText.includes('项目 A')`, 'name/description search')
  await click('项目 A', 'tbody tr')
  await visible('项目资料')
  await click('返回项目目录')
  assert.equal(await main.evaluate(`document.querySelector('[aria-label="搜索项目"]').value`), '修改后的项目 A')
  checkpoint('overview tabs expose only available capability; returning preserves search')

  // Real HTTP creates enough synthetic records to exercise actual pagination/scroll.
  for (let i = 1; i <= 55; i++) await api('/projects', { method: 'POST', body: { name: `批量项目 ${String(i).padStart(2, '0')}${i === 1 ? '长'.repeat(29) : ''}` } })
  await input('[aria-label="搜索项目"]', '批量项目')
  await choose('项目排序', 'name')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 50`, 'first directory page')
  await click('下一页')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 5`, 'second directory page')
  await click('批量项目 51', 'tbody tr')
  await visible('项目资料')
  await click('返回项目目录')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 5`, 'page restored')
  assert.equal(await main.evaluate(`document.querySelector('[aria-label="项目排序"]').dataset.choiceValue`), 'name')
  await click('上一页')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 50`, 'directory page one')
  const scroll = await main.evaluate(`(() => { const viewport = document.querySelector('[data-radix-scroll-area-viewport]'); viewport.scrollTop = 240; return {top:viewport.scrollTop, max:viewport.scrollHeight-viewport.clientHeight} })()`)
  assert.ok(scroll.max > 240 && scroll.top === 240, 'directory must have a usable contained scrollbar')
  await capture('directory')
  await click('批量项目 08', 'tbody tr')
  const beforeLeaveScroll = 240
  await visible('项目资料')
  await click('返回项目目录')
  await waitFor(main, `document.querySelector('[data-radix-scroll-area-viewport]')?.scrollTop >= ${beforeLeaveScroll}`, 'directory viewport restored')
  checkpoint('real 55-row query paginates, retains sorting/page and restores contained scroll')

  await input('[aria-label="搜索项目"]', '项目 A')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 1`, 'project A search')
  await click('项目 A', 'tbody tr')
  await visible('项目资料')
  await click('编辑项目')
  await input('#project-description', '冲突中保留的输入')
  const before = await api(`/projects/${a}`)
  await api(`/projects/${a}`, { method: 'PATCH', body: { description: '另一编辑者保存的资料', expectedManagementRevision: before.managementRevision } })
  await click('保存')
  await visible('基于最新内容重新编辑')
  assert.equal(await main.evaluate(`document.querySelector('#project-description').value`), '冲突中保留的输入')
  await capture('conflict')
  await click('基于最新内容重新编辑')
  await input('#project-description', '确认冲突后的资料')
  await click('保存')
  await closedForm()
  assert.equal((await api(`/projects/${a}`)).description, '确认冲突后的资料')
  checkpoint('real competing PATCH yields 409, preserves draft and explicitly rebases')

  await click('编辑项目')
  await input('#project-name', '重连后项目 A')
  const oldInstance = (await main.evaluate('window.autoflow.getRuntimeContext()')).sidecar.instanceId
  await main.evaluate('window.autoflow.restartSidecar()')
  await waitFor(main, `window.autoflow.getRuntimeContext().then(r => r.sidecar.state === 'ready' && r.sidecar.instanceId !== ${JSON.stringify(oldInstance)})`, 'new backend instance', 30000)
  await waitFor(main, `document.body.innerText.includes('本地服务正常') && !document.querySelector('#project-form button[type=submit]')?.disabled`, 'reconnected form')
  assert.equal(await main.evaluate(`document.querySelector('#project-name').value`), '重连后项目 A')
  await key('Escape')
  await visible('继续编辑')
  await capture('leave-confirmation')
  await click('继续编辑')
  assert.equal(await main.evaluate(`document.querySelector('#project-name').value`), '重连后项目 A')
  await click('保存')
  await closedForm()
  assert.equal((await api(`/projects/${a}`)).name, '重连后项目 A')
  checkpoint('same-workspace service restart preserves draft; Escape cancellation and later save work')

  // macOS Electron zoom, not a CSS simulation. The product's settings may offer fewer presets.
  await click('项目')
  await input('[aria-label="搜索项目"]', '')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 50`, 'directory ready before zoom')
  await native.evaluate('pm1Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2)')
  await waitFor(main, `innerWidth <= 720`, '200% layout applied')
  assert.equal(await native.evaluate('pm1Electron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()'), 2)
  const width = await main.evaluate(`({inner:innerWidth,root:document.querySelector('#root').getBoundingClientRect().width,doc:document.documentElement.scrollWidth})`)
  await click('', '[aria-label="项目排序"]')
  await waitFor(main, `Boolean(document.querySelector('[role=listbox]'))`, 'custom dropdown at 200%')
  const expanded = await main.evaluate(`({inner:innerWidth,root:document.querySelector('#root').getBoundingClientRect().width,doc:document.documentElement.scrollWidth})`)
  assert.equal(expanded.root, width.root)
  assert.equal(expanded.inner, width.inner)
  assert.ok(expanded.doc <= expanded.inner + 1)
  assert.ok(width.doc <= width.inner + 1, 'zoom must not cause page-wide overflow')
  const popup = await main.evaluate(`(() => { const r=document.querySelector('[role=listbox]').getBoundingClientRect(); return {top:r.top,bottom:r.bottom,height:r.height,viewportHeight:innerHeight} })()`)
  measurements.zoom = { factor: 2, before: width, after: expanded, popup }
  console.log(JSON.stringify(measurements.zoom))
  assert.ok(popup.top >= 0 && popup.bottom <= popup.viewportHeight, 'dropdown must fit the zoomed viewport')
  await capture('zoom-200-dropdown')
  await key('Escape')
  assert.equal(await main.evaluate('document.activeElement?.getAttribute("aria-label")'), '项目排序')
  await click('', '[aria-label="项目排序"]')
  await key('End'); await key('Enter')
  await waitFor(main, `document.querySelector('[aria-label="项目排序"]').dataset.choiceValue === '-name'`, 'keyboard reaches last zoomed option')
  await native.evaluate('pm1Electron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1)')
  checkpoint('200% Electron zoom and open dropdown preserve application width')

  await switchWorkspace()
  await visible('还没有项目')
  const c = await create('隔离项目 C', '第二工作区')
  assert.equal((await api('/projects')).total, 1)
  await switchWorkspace()
  await visible('新建项目')
  const restored = await api('/projects?pageSize=200')
  assert.equal(restored.total, 57)
  assert.ok(restored.items.some(p => p.projectId === a) && restored.items.some(p => p.projectId === b))
  assert.ok(!restored.items.some(p => p.projectId === c))
  checkpoint('two real workspaces isolate projects and switch back to saved data')

  for (const [label, expected] of [['浏览器配置', '新建配置'], ['代理管理', '代理管理'], ['模型管理', '模型管理'], ['设置', '工作区']]) { await click(label); await visible(expected) }
  await click('总览'); await visible('工作流工作台')
  await main.evaluate('window.autoflow.openAutomationStudio()')
  let studioTarget
  for (let i = 0; i < 50; i++) { studioTarget = (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.url.includes('view=automation-studio')); if (studioTarget) break; await wait(100) }
  assert.ok(studioTarget, 'Studio M1 entry retained')
  const studio = await connectCdp(studioTarget.webSocketDebuggerUrl)
  await waitFor(studio, `Boolean(document.querySelector('[aria-label="添加打开网页"]'))`, 'Studio M1 usable catalog')
  studio.close()
  await native.evaluate(`pm1Electron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).close()`)
  checkpoint('browser/proxy/model/settings/dashboard and Studio M1 entries regress successfully')

  const lastOpened = (await api(`/projects/${a}`)).lastOpenedAt
  assert.ok(lastOpened)
  native.close() // Disconnect Node inspector so normal app exit can complete.
  await main.evaluate('window.autoflow.quitApplication()')
  for (let i = 0; i < 150 && desktop.child.exitCode === null; i++) await wait(100)
  assert.equal(desktop.child.exitCode, 0)
  main.close(); native.close()
  await launch()
  await click('项目')
  assert.equal((await api(`/projects/${a}`)).lastOpenedAt, lastOpened)
  assert.equal((await api(`/projects/${a}`)).name, '重连后项目 A')
  await input('[aria-label="搜索项目"]', '重连后项目 A')
  await waitFor(main, `document.querySelectorAll('tbody tr').length === 1`, 'restarted project directory')
  await click('重连后项目 A', 'tbody tr')
  await visible('项目资料')
  await capture('restarted')
  checkpoint('full Electron restart retains projects and last-opened timestamps, then reopens A')
  const result = { scope: 'PM1 project entry and existing-module regression; PM2 data entry only; detailed data behavior not tested', result: 'passed', entry, platform: process.platform, arch: process.arch, checkedAt: new Date().toISOString(), checks, measurements, windows: 'not-run' }
  await writeFile(join(qa, `${entry}.json`), JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result, null, 2))
} catch (error) {
  try { await capture('failure'); console.error(await main.evaluate('({hash:location.hash,text:document.body.innerText})')) } catch { /* keep original failure */ }
  throw error
} finally {
  main?.close(); native?.close(); await stop(desktop?.child)
  await devServer?.close()
  await rm(userData, { recursive: true, force: true })
  await rm(otherWorkspace, { recursive: true, force: true })
}

async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.pm1Electron = process.getBuiltinModule('module').createRequire(process.cwd() + '/package.json')('electron'); true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await visible('本地服务正常', 30000)
}
function checkpoint(text) { checks.push(text); console.log(text) }
async function visible(text, timeout = 15000) { return waitFor(main, `Boolean(document.body?.innerText.includes(${JSON.stringify(text)}))`, text, timeout) }
async function api(path, options = {}) {
  const { sidecar } = await main.evaluate('window.autoflow.getRuntimeContext()')
  const response = await fetch(`${sidecar.baseUrl}/api/v1${path}`, { ...options, body: options.body ? JSON.stringify(options.body) : undefined, headers: { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': crypto.randomUUID() } })
  assert.ok(response.ok, `${options.method ?? 'GET'} ${path}: ${response.status}`)
  return response.json()
}
async function click(text, selector = 'button') {
  const point = await main.evaluate(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => !${JSON.stringify(text)} || e.textContent.trim() === ${JSON.stringify(text)} || e.getAttribute('aria-label') === ${JSON.stringify(text)} || (${JSON.stringify(selector)} === 'tbody tr' && e.firstElementChild?.textContent.trim() === ${JSON.stringify(text)})); if(!el) return null; el.scrollIntoView({block:'nearest'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
  assert.ok(point, `control missing: ${text || selector}`)
  await main.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await main.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 })
  await wait(120)
}
async function input(selector, value) {
  assert.equal(await main.evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)}); if(!el) return false; el.focus(); Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)}); el.dispatchEvent(new Event('input',{bubbles:true})); return true })()`), true)
  await wait(120)
}
async function key(key) { await main.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, ...(key === 'Enter' ? { text: '\r', unmodifiedText: '\r' } : {}), windowsVirtualKeyCode: key === 'Escape' ? 27 : key === 'Tab' ? 9 : key === 'End' ? 35 : 13 }); await main.command('Input.dispatchKeyEvent', { type: 'keyUp', key }); await wait(150) }
async function choose(label, value) { await click('', `[aria-label="${label}"]`); await click('', `[role=option][data-choice-value="${value}"]`) }
async function closedForm() { await waitFor(main, `!document.querySelector('#project-name')`, 'project form closes') }
async function create(name, description) {
  await click('新建项目'); await waitFor(main, `document.activeElement?.id === 'project-name'`, 'name autofocus'); await key('Tab'); assert.equal(await main.evaluate('document.activeElement.id'), 'project-description'); await input('#project-name', name); await input('#project-description', description); await capture('form'); if (name === '项目 B') { await main.evaluate(`document.querySelector('#project-name').focus()`); await key('Enter') } else await click('创建项目'); await closedForm(); await visible('项目资料')
  return (await api(`/projects?q=${encodeURIComponent(name)}`)).items.find(p => p.name === name).projectId
}
async function switchWorkspace() {
  const choice = await main.evaluate("window.autoflow.chooseWorkspace('previous')")
  assert.ok(choice.ok && choice.value)
  const switched = await main.evaluate(`window.autoflow.confirmWorkspace(${JSON.stringify(choice.value.id)})`, 30000)
  assert.equal(switched.ok, true)
  await visible('本地服务正常', 30000)
}
async function capture(name) { if (!main) return; const { data } = await main.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(join(qa, `${entry}-${name}.png`), data, 'base64') }
