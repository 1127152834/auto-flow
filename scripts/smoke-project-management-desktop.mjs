import assert from 'node:assert/strict'
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
async function click(text, selector = 'button') {
  const point = await waitFor(cdp, `(()=>{const elements=[...document.querySelectorAll(${JSON.stringify(selector)})];const e=elements.find(e=>e.getClientRects().length&&!e.disabled&&(e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}));if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `button ${text}`)
  for (const type of ['mousePressed', 'mouseReleased']) await cdp.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
}
async function fill(selector, value) {
  await waitFor(cdp, `Boolean(document.querySelector(${JSON.stringify(selector)}))`, selector)
  await cdp.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select()})()`)
  await cdp.command('Input.insertText', { text: value })
}
async function capture(name) {
  if (!options['output-dir']) return
  await mkdir(options['output-dir'], { recursive: true })
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png' })
  const filename = `project-${name}.png`
  await writeFile(join(options['output-dir'], filename), data, 'base64')
  report.screenshots.push(filename)
}
try {
  const browserVersion = options['runtime-kernel'] ? await installRuntimeKernel(options['runtime-kernel'], userData) : null
  sidecar = await launch()
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
