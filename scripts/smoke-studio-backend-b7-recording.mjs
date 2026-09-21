import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b7')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-recording-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b7-recording-'))
const checks = []
let clickCount = 0
let pageLoads = 0
const clickedBodies = []
let desktop, main, studio, native

const fixture = Buffer.from(`<!doctype html><html><head><meta charset="utf-8"><title>AutoFlow 录制页</title>
<style>#name,#submit{position:fixed;left:100px;width:400px;height:70px;font-size:24px}#name{top:180px}#submit{top:300px}</style></head>
<body><form id="record-form"><input id="name" aria-label="名称" autofocus><button id="submit" type="submit">确认录制</button></form><output id="result"></output>
<script>
fetch('/ready',{method:'POST'});
record_form=document.getElementById('record-form');
record_form.addEventListener('submit',event=>{event.preventDefault();const value=document.getElementById('name').value;result.textContent=value;fetch('/clicked',{method:'POST',headers:{'content-type':'text/plain'},body:value})});
</script></body></html>`)
const server = createServer((request, response) => {
  if (request.url === '/ready' && request.method === 'POST') { pageLoads += 1; response.writeHead(204).end(); return }
  if (request.url === '/clicked' && request.method === 'POST') {
    const chunks = []
    request.on('data', chunk => chunks.push(chunk))
    request.on('end', () => { clickedBodies.push(Buffer.concat(chunks).toString()); clickCount += 1; response.writeHead(204).end() })
    return
  }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'content-length': fixture.length })
  response.end(fixture)
})
await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen) })
const address = server.address()
assert.ok(address && typeof address === 'object')
const fixtureUrl = `http://127.0.0.1:${address.port}/recording`

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST', body: {
      name: 'B7 正式录制配置', description: '隔离工作区中的可见 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('临时工作区创建主应用 CloakBrowser Profile')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1800, height: 1200, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', 'B7 正式录制闭环')

  await openBrowserDialog(studio)
  await click(studio, '打开浏览器')
  await waitFor(studio, "document.body?.innerText.includes('关闭浏览器')", 'inspection browser open', 30_000)
  await setInput(studio, 'input[placeholder="https://example.com"]', fixtureUrl)
  await click(studio, '跳转')
  await waitForValue(async () => pageLoads > 0 ? true : null, 'recording fixture navigation', 15_000)
  await closeModernDialog(studio)
  checkpoint('通过正式浏览器面板打开可见 CloakBrowser 并导航到受控页面')

  await click(studio, '录制生成节点', '[aria-label="录制生成节点"]')
  await click(studio, '网页智能录制', '[role="menuitem"]')
  await waitFor(studio, "document.body?.innerText.includes('智能录制器')", 'recorder panel')
  await click(studio, '开始录制')
  await waitFor(studio, "document.body?.innerText.includes('录制中')", 'recording start', 15_000)

  await openBrowserDialog(studio)
  await click(studio, '聚焦目标页')
  await wait(300)
  enterRecordingThroughOs(userData, evidenceDir)
  await waitForValue(async () => clickCount === 1 ? true : null, 'trusted recorded click', 15_000)
  assert.equal(clickedBodies[0], 'formal-recording')
  await focusStudio(native)
  await closeModernDialog(studio)
  await waitFor(studio, "document.body?.innerText.includes('formal-recording') && document.body.innerText.includes('点击')", 'recorded steps rendered', 15_000)
  checkpoint('macOS 真实键盘输入和按钮操作由录制器采集并显示在正式审查面板')

  await click(studio, '停止录制')
  await waitFor(studio, "!document.body?.innerText.includes('录制中') && document.body?.innerText.includes('可拖删/排序后生成')", 'recording stop', 20_000)
  await click(studio, '保存审查')
  await waitFor(studio, "document.body?.innerText.includes('审查已保存')", 'review persisted')
  await click(studio, '预览生成')
  await waitFor(studio, `document.querySelector('[aria-label="录制生成预览"]')?.innerText.includes('打开网页')`, 'generation preview')
  checkpoint('停止后通过正式 UI 保存审查并预览生成节点')

  await click(studio, '生成节点')
  const generatedCount = await waitFor(studio, "document.querySelectorAll('.react-flow__node').length >= 3 && document.querySelectorAll('.react-flow__node').length", 'generated workflow nodes')
  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: B7 正式录制闭环')", 'workflow saved')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === 'B7 正式录制闭环')
  assert.ok(saved)
  assert.equal(saved.nodes.length, generatedCount)
  assert.ok(saved.nodes.some(node => node.data.moduleType === 'open_page'))
  assert.ok(saved.nodes.some(node => node.data.moduleType === 'input_text'))
  assert.ok(saved.nodes.some(node => node.data.moduleType === 'click_element'))
  checkpoint('录制步骤整批加入画布并经真实 HTTP/SQLite 保存')

  await openBrowserDialog(studio)
  await click(studio, '关闭浏览器')
  await waitFor(studio, "document.body?.innerText.includes('打开浏览器')", 'recording browser cleanup', 30_000)
  await closeModernDialog(studio)
  await waitForValue(async () => managedBrowserProcesses(userData).length === 0 ? true : null, 'recording browser process cleanup', 10_000)
  checkpoint('原录制浏览器通过正式 UI 关闭，进程树完成清理')

  await closeStudioNormally(native)
  await waitForNoStudioWindow(native)
  studio.close(); studio = undefined
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1800, height: 1200, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate(`document.querySelector('input[placeholder="工作流名称"]')?.value === 'B7 正式录制闭环' && document.querySelectorAll('.react-flow__node').length === ${generatedCount}`)) {
    await click(studio, '打开')
    await click(studio, '打开工作流 B7 正式录制闭环', '[role="button"]')
  }
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value === 'B7 正式录制闭环' && document.querySelectorAll('.react-flow__node').length === ${generatedCount}`, 'saved recording workflow reopen')
  checkpoint('正常关闭并重开 Studio 后恢复录制生成的节点、连线和配置')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const started = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0] ?? null, 'recorded workflow run', 20_000)
  const terminal = await waitForValue(async () => {
    const run = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(run.status) ? run : null
  }, 'recorded workflow terminal state', 120_000)
  assert.equal(terminal.status, 'completed')
  await waitForValue(async () => clickCount === 2 ? true : null, 'independent replay effect', 10_000)
  assert.deepEqual(clickedBodies, ['formal-recording', 'formal-recording'])
  await waitForValue(async () => managedBrowserProcesses(userData).length === 0 ? true : null, 'replay browser cleanup', 10_000)
  checkpoint('独立 CloakBrowser 重放保存流程，输入和点击副作用与录制一致并完成清理')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B7-recording-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: started.runId, generatedCount, clickCount, clickedBodies, checks,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'formal Studio UI through CDP plus macOS trusted keyboard events in CloakBrowser; no Store access', windowClose: 'BrowserWindow.close normal lifecycle; no destroy bypass' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, clickCount, clickedBodies, pageLoads, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  server.closeAllConnections()
  await new Promise(resolveClose => server.close(resolveClose))
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }
function managedBrowserProcesses(path) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(path) && /Chromium|CloakBrowser/.test(line)) }

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try {
      return await waitForValue(async () => {
        const targets = (await (await fetch(`${origin}/json/list`)).json()).filter(item => item.type === 'page' && item.url.includes('studio.html')).reverse()
        for (const target of targets) {
          try {
            const connection = await connectCdp(target.webSocketDebuggerUrl)
            if (await connection.evaluate("location.href.includes('studio.html')")) return connection
            connection.close()
          } catch { /* a closed BrowserWindow can briefly remain in the debugger target list */ }
        }
        return null
      }, 'Studio target', 8_000)
    } catch { /* dashboard may rerender while resources refresh */ }
  }
  throw new Error('正式 Studio 窗口未能从主界面打开')
}

async function openBrowserDialog(cdp) {
  await click(cdp, '自动化浏览器', '[aria-label="自动化浏览器"]')
  await waitFor(cdp, "Boolean(document.querySelector('.modern-dialog')) && document.body.innerText.includes('自动化浏览器')", 'automation browser dialog')
}
async function closeModernDialog(cdp) { await click(cdp, '', '.modern-dialog-header button') }

function enterRecordingThroughOs(workspacePath, evidencePath) {
  assert.equal(process.platform, 'darwin', '真实录制键盘验收当前仅在 macOS 实机执行')
  const browserPid = execFileSync('ps', ['-axo', 'pid=,command='], { encoding: 'utf8' })
    .split('\n')
    .map(line => line.trim().match(/^(\d+)\s+(.*)$/))
    .find(match => match && match[2].includes(workspacePath) && /Chromium\.app\/Contents\/MacOS\/Chromium\s/.test(match[2]) && !match[2].includes(' --type='))?.[1]
  assert.ok(browserPid, 'CloakBrowser main process unavailable for trusted keyboard input')
  const bounds = JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', `
    const se=Application('System Events');
    const p=se.applicationProcesses.whose({unixId:${browserPid}})()[0];
    p.frontmost=true; delay(0.3);
    JSON.stringify({position:p.windows[0].position(),size:p.windows[0].size()});
  `], { encoding: 'utf8' }))
  console.log(`CloakBrowser window ${JSON.stringify(bounds)}`)
  execFileSync('screencapture', ['-x', join(evidencePath, 'browser-focused.png')])
  execFileSync('osascript', [
    '-e', 'set the clipboard to "formal-recording"',
    '-e', 'tell application "System Events"',
    '-e', `set targetProcess to first application process whose unix id is ${browserPid}`,
    '-e', 'set frontmost of targetProcess to true',
    '-e', 'delay 0.3',
    '-e', 'keystroke "formal-recording"',
    '-e', 'delay 0.2',
    '-e', 'end tell',
  ])
  const buttonPoint = [bounds.position[0] + 300, bounds.position[1] + 456]
  execFileSync('/usr/bin/swift', ['-e', `
    import CoreGraphics
    import Foundation
    let point = CGPoint(x: ${buttonPoint[0]}, y: ${buttonPoint[1]})
    CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)?.post(tap: .cghidEventTap)
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)?.post(tap: .cghidEventTap)
    usleep(100000)
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)?.post(tap: .cghidEventTap)
  `])
  execFileSync('screencapture', ['-x', join(evidencePath, 'browser-after-input.png')])
}

async function focusStudio(nativeCdp) {
  assert.equal(await nativeCdp.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
}
async function closeStudioNormally(nativeCdp) {
  assert.equal(await nativeCdp.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;w.close();return true})()"), true)
}

async function waitForNoStudioWindow(nativeCdp) {
  await waitForValue(
    async () => await nativeCdp.evaluate("!qaElectron.BrowserWindow.getAllWindows().some(w=>w.getTitle().includes('工作流工作台'))"),
    'native Studio window close',
    15_000,
  )
}
async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) { last = await read(); if (last) return last; await wait(200) }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}
async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}
async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(100)
}
async function setInput(cdp, selector, value) {
  const p = await point(cdp, selector)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await wait(100)
}
async function capture(cdp, path) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}
